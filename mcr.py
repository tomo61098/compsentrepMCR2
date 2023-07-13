import torch
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

# rewrite
def get_data(bs, noise=0.1,contrastive=False,aug_noise=0.2):
    #For double swiss roll.
    x1, _ = datasets.make_swiss_roll(n_samples=bs//2,noise=noise)
    x2, _ = datasets.make_swiss_roll(n_samples=bs//2,noise=noise)
    x1 = np.stack([x1[:,0],x1[:,2]],axis=1)
    x2 = - np.stack([x2[:,0],x2[:,2]],axis=1)
    cluster_id = np.zeros((bs,))
    cluster_id[bs//2:] = 1
    x = np.concatenate([x1,x2],axis=0)
    
    if not contrastive:
        return torch.from_numpy(x), cluster_id
    else:
        x = torch.from_numpy(x)
        x_list = []
        x_list.append(x + aug_noise*torch.randn_like(x))
        x_list.append(x + aug_noise*torch.randn_like(x))
        return x_list, cluster_id

def chunk_avg(x,n_chunks=2,normalize=False):
    x_list = x.chunk(n_chunks,dim=0)
    x = torch.stack(x_list,dim=0)
    if not normalize:
        return x.mean(0)
    else:
        return F.normalize(x.mean(0),dim=1)

class MLP_net(nn.Module):
    def __init__(self,in_dim,dim,z_dim,n_clusters):
        super().__init__()
        self.backbone = nn.Sequential(
        nn.Linear(in_dim,dim),
        nn.ELU(),
        nn.Linear(dim,dim),
        nn.ELU()
        )
        self.subspace = nn.Linear(dim,z_dim)
        self.cluster = nn.Linear(dim,n_clusters)

    def forward_predict(self,x):
        feature = self.backbone(x)
        z, logits = self.subspace(feature), self.cluster(feature)
        z = F.normalize(z,dim=1)
        return z, logits

    def forward(self,x):
        feature = self.backbone(x)
        z = self.subspace(feature)
        return F.normalize(z,dim=1)

    def fit(self, X):
        #Train
        rng = np.random.default_rng()
        
        n_steps = 3000#0
        print_every = 50
        bs = 256

        #task variables
        #amb_dim = self.in_dim#2
        #z_dim = self.z_dim#6
        noise = 0.
        #n_clusters = self.n_clusters#2
        aug_noise = 0.005 

        net = self#MLP_net(amb_dim,128,z_dim,n_clusters)

        optimizer = optim.AdamW(net.parameters(),lr=0.001,betas=(0.9,0.99),weight_decay=0.00001)
        G_Softmax = Gumble_Softmax(0.2,straight_through=False)

        criterion = MaximalCodingRateReduction(eps=0.01,gamma=1.)
        criterion_z = Z_loss()

        for i in range(n_steps):
            batch = X[rng.choice(len(X), size=bs, replace=False)]
            x = [ batch * (1 + aug_noise * torch.randn(len(batch),1)), batch * (1 + aug_noise * torch.randn(len(batch), 1)) ]
            x = torch.cat(x,dim=0).float().cuda()

            z, logits = net.forward_predict(x)
            loss_z, z_sim = criterion_z(z)
            z_sim = z_sim.mean()

            prob = G_Softmax(logits)
            z, prob = chunk_avg(z,n_chunks=2,normalize=True), chunk_avg(prob,n_chunks=2)

            loss, loss_list= criterion(z,prob,num_classes=self.cluster.out_features)

            loss += 4000*loss_z

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if i%print_every == 0:
                print('{} steps done, loss c {}, loss d {}, z sim {}'.format(i+1,loss_list[0],loss_list[1],z_sim.item()))

    
class Gumble_Softmax(nn.Module):
    def __init__(self,tau, straight_through=False):
        super().__init__()
        self.tau = tau
        self.straight_through = straight_through
    
    def forward(self,logits):
        logps = torch.log_softmax(logits,dim=1)
        gumble = torch.rand_like(logps).log().mul(-1).log().mul(-1)
        logits = logps + gumble
        out = (logits/self.tau).softmax(dim=1)
        if not self.straight_through:
            return out
        else:
            out_binary = (logits*1e8).softmax(dim=1).detach()
            out_diff = (out_binary - out).detach()
            return out_diff + out
    
class Z_loss(nn.Module):
    def __init__(self):
        super().__init__()
        #only supports 2 views
        
    def forward(self,z):
        z_list = z.chunk(2,dim=0)
        z_sim = F.cosine_similarity(z_list[0],z_list[1],dim=1)
        z_sim_out = z_sim.clone().detach()
        loss = - z_sim.mean()
        return loss, z_sim_out

class MaximalCodingRateReduction(torch.nn.Module):
    def __init__(self, eps=0.01, gamma=1):
        super(MaximalCodingRateReduction, self).__init__()
        self.eps = eps
        self.gamma = gamma
        
    def compute_discrimn_loss(self, W):
        """Discriminative Loss."""
        p, m = W.shape
        I = torch.eye(p,device=W.device)
        scalar = p / (m * self.eps)
        logdet = torch.logdet(I + scalar * W.matmul(W.T))
        return logdet / 2.
    
    def compute_compress_loss(self, W, Pi):
        p, m = W.shape
        k, _, _ = Pi.shape
        I = torch.eye(p,device=W.device).expand((k,p,p))
        trPi = Pi.sum(2) + 1e-8
        scale = (p/(trPi*self.eps)).view(k,1,1)
        
        W = W.view((1,p,m))
        log_det = torch.logdet(I + scale*W.mul(Pi).matmul(W.transpose(1,2)))
        compress_loss = (trPi.squeeze()*log_det/(2*m)).sum()
        return compress_loss
        
    def forward(self, X, Y, num_classes=None):
        #This function support Y as label integer or membership probablity.
        if len(Y.shape)==1:
            #if Y is a label vector
            if num_classes is None:
                num_classes = Y.max() + 1
            Pi = torch.zeros((num_classes,1,Y.shape[0]),device=Y.device)
            for indx, label in enumerate(Y):
                Pi[label,0,indx] = 1
        else:
            #if Y is a probility matrix
            if num_classes is None:
                num_classes = Y.shape[1]
            Pi = Y.T.reshape((num_classes,1,-1))
            
        W = X.T
        discrimn_loss = self.compute_discrimn_loss(W)
        compress_loss = self.compute_compress_loss(W, Pi)
 
        total_loss = - discrimn_loss + self.gamma*compress_loss
        return total_loss, [discrimn_loss.item(), compress_loss.item()]
