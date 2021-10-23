
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