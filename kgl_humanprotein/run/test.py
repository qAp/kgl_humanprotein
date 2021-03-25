# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/08_run.test.ipynb (unless otherwise specified).

__all__ = ['dummy_predict_image', 'write_dummy_submission', 'datasets_names', 'split_names', 'augment_list', 'test',
           'predict', 'prob_to_result', 'organise_results', 'write_submission_csv']

# Cell

import os, sys
import argparse
from tqdm import tqdm
import numpy as np
import pandas as pd
from pathlib import Path
import cv2
import pycocotools.mask as mutils

import torch
import torch.optim
from torch.utils.data import DataLoader
from torch.utils.data.sampler import SequentialSampler
from torch.nn import DataParallel
import torch.nn.functional as F
from torch.autograd import Variable

from ..config.config import *
from ..data_process import *
from ..utils.common_util import *
from ..networks.imageclsnet import init_network
from ..datasets.protein_dataset import ProteinDataset
from ..utils.augment_util import *
from ..utils.log_util import Logger

# Cell

def dummy_predict_image(img):
    pred = 0
    conf = .5

    height, width = img.shape[:2]
    bmask = np.zeros((height, width), dtype=np.uint8)
    bmask[:height//3, :width//3] = 1

    rle = mutils.encode(np.asfortranarray(bmask))
    coco_rle = {'size': [height, width], 'counts': rle}
    return pred, conf, rle


def write_dummy_submission(dir_test, imgids, dst=Path('./')):

    with open(dst/'submission.csv', mode='w') as f:
        print(
            'ID,ImageWidth,ImageHeight,PredictionString', file=f)

        for imgid in imgids:
            img = load_RGBY_image(dir_test, imgid)

            pred, conf, rle = dummy_predict_image(img)
            bmask = mutils.decode(rle)
            rle = encode_binary_mask(bmask.astype(bool))

            predstring = f'{pred} {conf} {rle}'

            height, width = img.shape[:2]
            submn_img = f'{imgid}, {width}, {height}, {predstring}'
            print(submn_img, file=f)

# Cell

datasets_names = ['test', 'val']
split_names = ['random_ext_folds5',
               'random_ext_noleak_clean_folds5']
augment_list = ['default', 'flipud', 'fliplr','transpose',
                'flipud_lr', 'flipud_transpose', 'fliplr_transpose',
                'flipud_lr_transpose']

# Cell

def test(out_dir,
         gpu_id='0', arch='class_densenet121_dropout',
         num_classes=19, in_channels=4, img_size=768, crop_size=512,
         batch_size=32, workers=3, pin_memory=True,
         seed=100, seeds=None, fold=0, augment='default',
         dataset='test', split_name='random_ext_folds5',
         predict_epoch=None):
    '''
    PyTorch Protein Classification

    Args:
        out_dir (str): Name of directory where model is saved.  This will
            also be used to name a newly created directory for saving the
            predicted results.
        gpu_id (str): GPU id used for predicting. Default: ``'0'``
        arch (str): Model architecture. Default: ``'class_densenet121_dropout)'``
        num_classes (int): Number of classes. Default: 19
        in_channels (int): In channels. Default: 4
        img_size (int):  Image size. Default: 768
        crop_size (int): Crop size. Default: 512
        batch_size (int): Train mini-batch size. Default: 32
        workers (int): Number of data loading workers. Default: 3
        pin_memory (bool): DataLoader's ``pin_memory`` argument.
        fold (int): Index of fold. Default: 0
        augment (str):  Comma-separated string of one or more of
            the following: ``'default'``, ``'flipud'``, ``'fliplr'``,
            ``'transpose'``, ``'flipud_lr'``, ``'flipud_transpose'``,
            ``'fliplr_transpose'``, ``'flipud_lr_transpose'``.
            Default: ``'default'``
        seed (int):  Random seed. Default: 100
        seeds (str): Predict seed. Default: None
        dataset (str, optional): ``'test'``, or ``'val'``. Default: ``'test'``
        split_name (str, optional): ``'random_ext_folds5'``, or
            ``'random_ext_noleak_clean_folds5'``. Default: 'random_ext_folds5'
        predict_epoch (int): Number epoch to predict. Default: None
    '''
    if dataset not in datasets_names:
        print(f'`dataset` needs to be one of {datasets_names}.')
        raise

    if split_name not in split_names:
        print(f'`split_name` must be one of {split_names}.')
        raise

    log_out_dir = opj(RESULT_DIR, 'logs', out_dir, 'fold%d' % fold)
    if not ope(log_out_dir):
        os.makedirs(log_out_dir)
    log = Logger()
    log.open(opj(log_out_dir, 'log.submit.txt'), mode='a')

    predict_epoch = 'final' if predict_epoch is None else '%03d' % predict_epoch
    network_path = opj(RESULT_DIR, 'models', out_dir, 'fold%d' % fold, '%s.pth' % predict_epoch)

    submit_out_dir = opj(RESULT_DIR, 'submissions', out_dir, 'fold%d' % fold, 'epoch_%s' % predict_epoch)
    log.write(">> Creating directory if it does not exist:\n>> '{}'\n".format(submit_out_dir))
    if not ope(submit_out_dir):
        os.makedirs(submit_out_dir)

    # setting up the visible GPU
    os.environ['CUDA_VISIBLE_DEVICES'] = gpu_id

    augment = augment.split(',')
    for augment_ in augment:
        if augment_ not in augment_list:
            raise ValueError('Unsupported or unknown test augmentation: {}!'.format(augment))

    model_params = {}
    model_params['architecture'] = arch
    model_params['num_classes'] = num_classes
    model_params['in_channels'] = in_channels
    model = init_network(model_params)

    log.write(">> Loading network:\n>>>> '{}'\n".format(network_path))
    checkpoint = torch.load(network_path)
#     _, in_features = checkpoint['state_dict']['logit.weight'].shape
#     logit_weight = torch.randn(num_classes, in_features)
#     logit_bias = torch.randn(num_classes)
#     checkpoint['state_dict']['logit.weight'] = logit_weight
#     checkpoint['state_dict']['logit.bias'] = logit_bias
    model.load_state_dict(checkpoint['state_dict'])
    log.write(">>>> loaded network:\n>>>> epoch {}\n".format(checkpoint['epoch']))

    # moving network to gpu and eval mode
    model = DataParallel(model)
    model.to(DEVICE)
    model.eval()

    # Data loading code
    if dataset == 'test':
        test_split_file = DATA_DIR/'split'/'test_27.feather'
    elif dataset == 'val':
        test_split_file = opj(DATA_DIR, 'split', split_name, 'random_valid_cv%d.csv' % fold)
    else:
        raise ValueError('Unsupported or unknown dataset: {}!'.format(dataset))

    test_dataset = ProteinDataset(
        test_split_file,
        img_size=img_size,
        is_trainset=(dataset != 'test'),
        return_label=False,
        in_channels=in_channels,
        transform=None,
        crop_size=crop_size,
        random_crop=False)

    test_loader = DataLoader(
        test_dataset,
        sampler=SequentialSampler(test_dataset),
        batch_size=batch_size,
        drop_last=False,
        num_workers=workers,
        pin_memory=pin_memory)

    seeds = [seed] if seeds is None else [int(i) for i in seeds.split(',')]
    for seed in seeds:
        test_dataset.random_crop = (seed != 0)
        for augment_ in augment:
            test_loader.dataset.transform = eval('augment_%s' % augment_)
            if crop_size > 0:
                sub_submit_out_dir = opj(submit_out_dir, '%s_seed%d' % (augment_, seed))
            else:
                sub_submit_out_dir = opj(submit_out_dir, augment_)
            if not ope(sub_submit_out_dir):
                os.makedirs(sub_submit_out_dir)
            with torch.no_grad():
                predict(test_loader, model, sub_submit_out_dir, dataset)

    return submit_out_dir



def predict(test_loader, model, submit_out_dir, dataset):
    all_probs = []
    img_ids = np.array(test_loader.dataset.img_ids)
    for it, iter_data in tqdm(enumerate(test_loader, 0), total=len(test_loader)):
        images, indices = iter_data
        images = Variable(images.to(DEVICE), volatile=True)
        outputs = model(images)
        logits = outputs

        probs = F.sigmoid(logits).data
        all_probs += probs.cpu().numpy().tolist()
    img_ids = img_ids[:len(all_probs)]
    all_probs = np.array(all_probs).reshape(len(img_ids), -1)

    np.save(opj(submit_out_dir, 'prob_%s.npy' % dataset), all_probs)

    result_df = prob_to_result(all_probs, img_ids)
    result_df.to_csv(opj(submit_out_dir, 'results_%s.csv.gz' % dataset), index=False, compression='gzip')

def prob_to_result(probs, img_ids, th=0.5):
    probs = probs.copy()
    probs[np.arange(len(probs)), np.argmax(probs, axis=1)] = 1

    pred_list = []
    for line in probs:
        s = ' '.join(list([str(i) for i in np.nonzero(line > th)[0]]))
        pred_list.append(s)
    result_df = pd.DataFrame({ID: img_ids, PREDICTED: pred_list})
    return result_df

# Cell

def organise_results(df_cells, dir_results):
    if isinstance(dir_results, str):
        dir_results = Path(dir_results)

    preds = pd.read_csv(
        dir_results/'default_seed0'/'results_test.csv.gz')
    probs = np.load(dir_results/'default_seed0'/'prob_test.npy')

    preds = pd.merge(
        df_cells, preds, left_on='Id', right_on='Id', how='inner')

    preds['Image_Id'] = preds.apply(
        lambda o: o['Id'].split('_')[0], axis=1)

    return preds, probs

# Cell

def write_submission_csv(preds, probs, dir_out=Path('/kaggle/working')):

    with open(dir_out / 'submission.csv', mode='w') as f_submission:
        print('ID,ImageWidth,ImageHeight,PredictionString',
              file=f_submission)

        for imgid, df in preds.groupby('Image_Id'):

            pred_string = []
            for i, r in df.iterrows():

                bmask = mutils.decode(r['rle'])
                rle = encode_binary_mask(bmask.astype(bool))

                labels = r['Predicted'].split()
                labels = np.array([int(label) for label in labels])

                confidences = probs[i, labels]

                # To debug submission,
                # include just the first predicted label
                labels, confidences = labels[:1], confidences[:1]

                for label, confidence in zip(labels, confidences):
                    pred_string.append(f'{label} {confidence} {rle}')

            pred_string = ' '.join(pred_string)

            img_h, img_w = df.iloc[0]['rle']['size']
            img_string = f'{imgid}, {img_w}, {img_h}, {pred_string}'

            print(img_string, file=f_submission)
