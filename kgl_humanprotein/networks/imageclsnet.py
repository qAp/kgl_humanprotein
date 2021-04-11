# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06_networks.imageclsnet.ipynb (unless otherwise specified).

__all__ = ['init_network', 'model_names']

# Cell
import torch

from ..config.config import *
from ..utils.common_util import *
from .densenet import class_densenet121_dropout, class_densenet121_large_dropout
from .inception_v3 import class_inceptionv3_dropout
from .resnet import class_resnet34_dropout, class_resnet18_dropout

# Cell

model_names = {
    'class_densenet121_dropout': 'densenet121-a639ec97.pth',
    'class_densenet121_large_dropout': 'densenet121-a639ec97.pth',
    'class_inceptionv3_dropout': 'inception_v3_google-1a9a5a14.pth',
    'class_resnet34_dropout': 'resnet34-333f7ec4.pth',
    'class_resnet18_dropout': 'resnet18-5c106cde.pth',
}

def init_network(params, model_multicell=None):
    architecture = params.get('architecture', 'class_densenet121_dropout')
    num_classes = params.get('num_classes', 28)
    in_channels = params.get('in_channels', 4)

    pretrained_file = opj(PRETRAINED_DIR, model_names[architecture])
    print(">> Using pre-trained model.")
    net = eval(architecture)(num_classes=num_classes, in_channels=in_channels, pretrained_file=pretrained_file)

    if model_multicell:
        print('>> Loading multi-cell model.')
        state = torch.load(model_multicell)['state_dict']
        _, in_features = state['logit.weight'].shape
        logit_weight = torch.randn(num_classes, in_features)
        logit_bias = torch.randn(num_classes)
        state['logit.weight'] = logit_weight
        state['logit.bias'] = logit_bias
        net.load_state_dict(state)
    return net