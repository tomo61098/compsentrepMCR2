## Compressing Sentence Representation with Maximum Coding Rate Reduction

This code was adapted from [Homomorphic projective distillation (HPD) for sentence embedding](https://github.com/XuandongZhao/HPD) and [Neural Manifold Clustering and Embedding (NMCE)](https://github.com/zengyi-li/NMCE-release).

By running the script

```bash
bash run_emb.sh
```
we store all embeddings.

Then we can train the model by running the script

```bash
bash run.sh
```

To evaluate the model run

```bash
bash run_eval.sh
```
which should give something like

```
------ test ------
+-------+-------+-------+-------+-------+--------------+-----------------+-------+
| STS12 | STS13 | STS14 | STS15 | STS16 | STSBenchmark | SICKRelatedness |  Avg. |
+-------+-------+-------+-------+-------+--------------+-----------------+-------+
| 73.57 | 83.90 | 79.88 | 85.63 | 81.05 |    83.22     |      76.10      | 80.48 |
+-------+-------+-------+-------+-------+--------------+-----------------+-------+
```

Default values for the embeddings are `nli-mpnet-base-v2` as the teacher model and MCR2 as the projection loss.
We append two linear layers each followed by ELU to fit the projection using MCR2 and train it for 3000 iterations likewith the NMCE approach.
Default output dimension is 128.

The student model `nreimers/MiniLM-L6-H384-uncased` is trained on the before embedded data like in HPD but with 100 epochs.