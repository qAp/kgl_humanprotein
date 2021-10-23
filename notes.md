
# What this challenge is about?
This is challenge is the Human Protain Atlas (HPA) Single-cell Classification challenge.

1. Segment cells.
2. Identify in each cell which of the 18 possible proteins there are, if any.

# Available to the competitors
The host provided:
1. Images containing cells
2. Protein labels for each image.
3. A performant cell segmentation model.

This problem is a "weakly supervised multi-label classification problem".  The host explains that they think some cells might contain none of the 18 possible protein labels, but this occurrence should be rare.

The main problem is about going from image-level labels to cell-level labels.

# The images 
1. Each image has 4 colour channels: red, green, blue, and yellow.
2. Each channel is provided in its own tif file. 

# The labels
1. The number of proteins in the images ranges from 1 to 5.
2. Roughly half of the images have a single protein type. i.e. a single image-level label.
3. The number of images decreases with the number of protein types.  The distribution is skewed right. 

# Main approach
Turn @bestfitting's image-level protein classifier into a cell-level protein classifier.

There was a previous related competition where the goal is to predict protein labels for an entire image of cells.  @bestfitting's winning solution is documented in a paper and the code on github, so instead of using that model to look at an image of cells, maybe I could use it to look at an image of a cell.  

Adapting @bestfitting's solution saves time spent writing code, and also the associated model has already been trained on cell images, which gives an advantage over using a model pre-trained only on ImageNet.  @bestfitting is a top Kaggler, studying and using his code is a good learning opportunity.  

# Generating cell-level labels for training
[histogram of image count vs number of proteins]

1. If the image-level label contains more than 1 protein, then we cannot be sure what combinations of these each cell has.
2. So I first work with image-level labels which contain just 1 protein.  In these images, each cell can only have that one protein, so I can label the cell with certainty. 
3. Crop out cells and mask the background using the provided cell segmentation model.
4. In the resulting training set, each image contains one cell and is labelled with one protein type.

# Training on labelled cells
1. Simply trained @bestfitting's winning model on the training set made above, using the same setup.

# Generating cell-level pseudo-labels for training
1. Take the trained model from above.
2. Take cells with image-level labels containing more than 1 protein.
3. For each cell that is passed through the model, you get 18 probabilities, one for each protein type.
4. If a probability value is greater than 0.5 and if its corresponding protein type is in the image-level label, then assign this protein type as a cell-level label to the cell.  
5. This way it was possible to produce samples where the cell-level label contains multiple protein types.  

# Train further
1. Add these pseudo-labelled samples to the previous training set.
2. Train further to get the final model.

# Inference
[diagram]
1. Make cell crops using the provided cell segmentation model.
2. Use the final model to classify the protein types of each cell crop.


# Class Imbalance
[Number of occurence for each protein type]
[The pairwise occurence count matrix]

1. Even though the ground-truth label for each cell is not given, it's observed that the dataset is imbalanced in several ways.
2. I tried to balance the number of occurences of each protein type.
3. Reduce the number of samples for over-represented protein types.
4. Download and process more images from the Human Protain Altas to bump up the number of samples for under-represented protein types, such as 11. 

# Working on Kaggle
1. Training set is 10+ GB, so had to spread it across 5 Kaggle Notebooks and Datasets.
2. Development workflow: 
  - local CPU + nbdev
  - Kaggle GPUs (40 hours per week)





