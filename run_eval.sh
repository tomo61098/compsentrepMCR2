list=(./output/HPD-F128*)
slist=$(echo $list | sort)
ele=${list[-1]}
echo $ele
python senteval.py --pooler avg --task_set sts --mode test --cuda cuda:0 --model_type st --model_name_or_path $ele
# --tasks STS13
