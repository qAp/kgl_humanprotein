# kgl_humanprotein
> A top 12% solution for Human Protein Atlas Single-cell Classification Kaggle


Competition page: https://www.kaggle.com/c/hpa-single-cell-image-classification/

## Main approach

1. No segmentation training.
2. Train classifier on single-label cells.
3. Generate labels for multi-label images' cells using model from step 2.
4. Train classifier on single-label cells and cells with generated labels.

## What didn't work well

1. The use of 'soft' labels.  

# Reference & Resources

- https://github.com/CellProfiling/HPA-competition-solutions/tree/master/bestfitting
- https://www.kaggle.com/its7171/mmdetection-for-segmentation-training
- https://www.kaggle.com/its7171/mmdetection-for-segmentation-inference
- https://www.kaggle.com/lnhtrang/hpa-public-data-download-and-hpacellseg
- https://www.kaggle.com/dschettler8845/hpa-cellwise-classification-inference
- https://www.kaggle.com/dschettler8845/hpa-cellwise-classification-training
- https://www.kaggle.com/thedrcat/hpa-single-cell-classification-eda
- https://www.kaggle.com/c/hpa-single-cell-image-classification/discussion/216430
