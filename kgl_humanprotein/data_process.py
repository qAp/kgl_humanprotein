# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/02_data_process.ipynb (unless otherwise specified).

__all__ = ['imgids_from_directory', 'imgids_testing', 'read_img', 'load_RGBY_image', 'save_image', 'CellSegmentator',
           'load_segmentator', 'get_cellmask', 'encode_binary_mask', 'coco_rle_encode', 'rle_encode', 'rle_decode',
           'mask2rles', 'rles2bboxes', 'segment_image', 'segment_images', 'resize_image', 'crop_image',
           'remove_faint_greens', 'pad_to_square']

# Cell
import os
import ast
from pathlib import Path
from itertools import groupby
import functools
import mlcrate
from multiprocessing import Pool
from pycocotools import mask as mutils
from pycocotools import _mask as coco_mask
import numpy as np
import pandas as pd
import cv2, PIL
import zlib
import base64
import zipfile
import uuid

from .config.config import *
from .utils.common_util import *

# Cell
def imgids_from_directory(path):
    if isinstance(path, str):
        path = Path(path)

    imgids = set(n.stem.split('_')[0] for n in path.iterdir())
    return list(imgids)

# Cell
imgids_testing = [
    '000a6c98-bb9b-11e8-b2b9-ac1f6b6435d0',
    '001838f8-bbca-11e8-b2bc-ac1f6b6435d0',
    '000c99ba-bba4-11e8-b2b9-ac1f6b6435d0',
    'a34d8680-bb99-11e8-b2b9-ac1f6b6435d0',
    '000a9596-bbc4-11e8-b2bc-ac1f6b6435d0']

# Cell

def read_img(dir_data, image_id, color, image_size=None, suffix='.png'):
    filename = dir_data/f'{image_id}_{color}{suffix}'
    assert filename.exists(), f'not found {filename}'

    img = cv2.imread(str(filename), cv2.IMREAD_UNCHANGED)

    if image_size is not None:
        img = cv2.resize(img, (image_size, image_size))

    if img.max() > 255:
        img_max = img.max()
        img = (img/255).astype('uint8')

    return img



def load_RGBY_image(dir_data, image_id,
                    rgb_only=False, suffix='.png', image_size=None):

    red, green, blue = [
        read_img(dir_data, image_id, color, image_size, suffix)
        for color in ('red', 'green', 'blue')]

    channels = [red, green, blue]

    if not rgb_only:
        yellow = read_img(
            dir_data, image_id, "yellow", image_size, suffix)
        channels.append(yellow)

    stacked_images = np.transpose(np.array(channels), (1, 2, 0))

    return stacked_images

# Cell

def save_image(dst, imgid, img):
    dst = Path(dst)
    for ch, color in enumerate(['red', 'green', 'blue', 'yellow']):
        cv2.imwrite(str(dst / f'{imgid}_{color}.png'), img[..., ch])


# Cell

import hpacellseg.cellsegmentator as cellsegmentator
from hpacellseg.utils import label_cell, label_nuclei
from tqdm import tqdm

class CellSegmentator(cellsegmentator.CellSegmentator):
    def __init__(self, nuc_model, cell_model, *args, **kwargs):
        nuc_model = str(nuc_model)
        cell_model = str(cell_model)
        super().__init__(nuc_model, cell_model, *args, **kwargs)

    def __call__(self, red, yellow, blue):
        '''
        `red`: list
          Red images' file paths.
        `yellow`: list
          Yellow images' file paths.
        `blue`: list
          Blue images' file paths.
        '''
        assert len(red) == len(yellow) == len(blue)

        if isinstance(red[0], Path):
            red, yellow, blue = (
                [str(n) for n in fns]
                for fns in [red, yellow, blue])

        segs_nucl = self.pred_nuclei(blue)
        segs_cell = self.pred_cells([red, yellow, blue])

        masks = []
        for seg_nucl, seg_cell in zip(segs_nucl, segs_cell):
            mask_nucl, mask_cell = label_cell(seg_nucl, seg_cell)
            masks.append((mask_nucl, mask_cell))

        return masks



def load_segmentator(
    dir_segmentator_models, scale_factor=0.25, device="cuda",
    padding=True, multi_channel_model=True):

    model_nucl = dir_segmentator_models / 'nuclei-model.pth'
    model_cell = dir_segmentator_models / 'cell-model.pth'

    segmentator = CellSegmentator(
        model_nucl, model_cell,
        scale_factor=scale_factor, device=device, padding=padding,
        multi_channel_model=multi_channel_model)

    return segmentator



def get_cellmask(img, segmentator):
    img_r, img_y, img_b = img[...,0], img[...,3], img[...,2]

    masks = segmentator(red=[img_r], yellow=[img_y], blue=[img_b])

    _, mask = masks[0]
    return mask

# Cell

def encode_binary_mask(mask):
    """Converts a binary mask into OID challenge encoding ascii text."""

    # check input mask --
    if mask.dtype != np.bool:
        raise ValueError(
        "encode_binary_mask expects a binary mask, received dtype == %s" %
        mask.dtype)

    mask = np.squeeze(mask)
    if len(mask.shape) != 2:
        raise ValueError(
        "encode_binary_mask expects a 2d mask, received shape == %s" %
        mask.shape)

    # convert input mask to expected COCO API input --
    mask_to_encode = mask.reshape(mask.shape[0], mask.shape[1], 1)
    mask_to_encode = mask_to_encode.astype(np.uint8)
    mask_to_encode = np.asfortranarray(mask_to_encode)

    # RLE encode mask --
    encoded_mask = coco_mask.encode(mask_to_encode)[0]["counts"]

    # compress and base64 encoding --
    binary_str = zlib.compress(encoded_mask, zlib.Z_BEST_COMPRESSION)
    base64_str = base64.b64encode(binary_str)
    return base64_str.decode()


def coco_rle_encode(bmask):
    rle = {'counts': [], 'size': list(bmask.shape)}
    counts = rle.get('counts')
    for i, (value, elements) in enumerate(groupby(bmask.ravel(order='F'))):
        if i == 0 and value == 1:
            counts.append(0)
        counts.append(len(list(elements)))
    return rle

# Cell

def rle_encode(img, mask_val=1):
    """
    Turns our masks into RLE encoding to easily store them
    and feed them into models later on
    https://en.wikipedia.org/wiki/Run-length_encoding

    Args:
        img (np.array): Segmentation array
        mask_val (int): Which value to use to create the RLE

    Returns:
        RLE string

    """
    dots = np.where(img.T.flatten() == mask_val)[0]
    run_lengths = []
    prev = -2
    for b in dots:
        if (b>prev+1): run_lengths.extend((b + 1, 0))
        run_lengths[-1] += 1
        prev = b

    return ' '.join([str(x) for x in run_lengths])


def rle_decode(rle_string, height, width):
    """ Convert RLE sttring into a binary mask

    Args:
        rle_string (rle_string): Run length encoding containing
            segmentation mask information
        height (int): Height of the original image the map comes from
        width (int): Width of the original image the map comes from

    Returns:
        Numpy array of the binary segmentation mask for a given cell
    """
    rows,cols = height,width
    rle_numbers = [int(num_string) for num_string in rle_string.split(' ')]
    rle_pairs = np.array(rle_numbers).reshape(-1,2)
    img = np.zeros(rows*cols,dtype=np.uint8)
    for index,length in rle_pairs:
        index -= 1
        img[index:index+length] = 255
    img = img.reshape(cols,rows)
    img = img.T
    img = (img / 255).astype(np.uint8)
    return img


# Cell

def mask2rles(mask):
    '''
    Args:
        mask (np.array): 2-D array with discrete values each
            representing a different class or object.
        rles (list): COCO run-length encoding:
            {'size': [height, width],
             'counts': encoded RLE}
    '''
    ids_cell = np.unique(mask)

    rles = []
    for id in ids_cell:
        if id == 0:
            continue

        bmask = np.where(mask == id, 1, 0)
        bmask = np.asfortranarray(bmask).astype(np.uint8)
        rle = mutils.encode(bmask)
        rles.append(rle)

    return rles

# Cell
def rles2bboxes(rles):
    if len(rles) == 0:
        return []

    bboxes = mutils.toBbox(rles)
    bboxes[:,2] += bboxes[:,0]
    bboxes[:,3] += bboxes[:,1]

    return bboxes

# Cell

def segment_image(dir_img=None, imgid=None, segmentator=None):
    img = load_RGBY_image(dir_img, imgid)
    mask = get_cellmask(img, segmentator)
    rles = mask2rles(mask)
    bboxes = rles2bboxes(rles)

    ids = [f'{imgid}_{i}' for i in range(len(rles))]
    df = pd.DataFrame(
        {'Id': ids, 'rle': rles, 'bbox': list(bboxes)})

    return df



def segment_images(dir_img, imgids, segmentator):
    df = pd.DataFrame()
    for imgid in tqdm(imgids, total=len(imgids)):
        df_img = segment_image(dir_img, imgid, segmentator)
        df = df.append(df_img, ignore_index=True)

    return df

# Cell

def resize_image(img, sz):
    return cv2.resize(img, (sz, sz), interpolation=cv2.INTER_LINEAR)

# Cell

def crop_image(img, bbox, bmask=None):
    '''
    Args:
        img (np.array): Image to be cropped by ``bbox``.
        bbox (np.array): Bounding box in terms of [x0, y0, x1, y1].
        bmask (np.array, np.uint8): Binary mask for the cell.
    '''
    bbox = bbox.astype(np.int16)
    x0, y0, x1, y1 = bbox

    crop = img[y0:y1, x0:x1]

    if bmask is not None:
        crop = bmask[y0:y1, x0:x1][...,None] * crop

    return crop

# Cell

def remove_faint_greens(xs, crops, green_thres=64):
    assert len(xs) == len(crops)
    xs_out = []
    for x, crop in zip(xs, crops):
        if crop[...,1].max() > green_thres:
            xs_out.append(x)
    return xs_out

# Cell

def pad_to_square(img):
    '''
    Pad an image to a square size, centering it as much as possible.
    '''
    h, w, c = img.shape
    if h == w:
        return img
    elif h < w:
        img_padded = np.zeros((w, w, c), dtype=img.dtype)
        offset0 = (w - h) // 2
        offset1 = (w - h) - offset0
        img_padded[offset0:-offset1, :] = img.copy()
    else:
        img_padded = np.zeros((h, h, c), dtype=img.dtype)
        offset0 = (h - w) // 2
        offset1 = (h - w) - offset0
        img_padded[:, offset0:-offset1] = img.copy()
    return img_padded