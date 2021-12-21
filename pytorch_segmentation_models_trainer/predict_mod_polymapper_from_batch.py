# -*- coding: utf-8 -*-
"""
/***************************************************************************
 pytorch_segmentation_models_trainer
                              -------------------
        begin                : 2021-12-15
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Philipe Borba - Cartographic Engineer
                                                            @ Brazilian Army
        email                : philipeborba at gmail dot com
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ****
"""
import concurrent.futures
from concurrent.futures.thread import ThreadPoolExecutor
import itertools
import logging
from pathlib import Path

from pytorch_lightning.trainer.trainer import Trainer
from pytorch_segmentation_models_trainer.dataset_loader.dataset import ImageDataset
from pytorch_segmentation_models_trainer.predict import (
    instantiate_model_from_checkpoint,
    instantiate_polygonizer,
)
from pytorch_segmentation_models_trainer.tools.parallel_processing.process_executor import (
    Executor,
)
from typing import Dict, List

import hydra
import numpy as np
import omegaconf
import torch
from hydra.utils import instantiate
from omegaconf import DictConfig
from omegaconf.omegaconf import OmegaConf
from tqdm import tqdm

from pytorch_segmentation_models_trainer.tools.inference.inference_processors import (
    AbstractInferenceProcessor,
)
from pytorch_segmentation_models_trainer.tools.polygonization.polygonizer import (
    TemplatePolygonizerProcessor,
)
from pytorch_segmentation_models_trainer.utils.os_utils import import_module_from_cfg
from functools import partial
import copy
import albumentations as A
from albumentations.pytorch import ToTensorV2
import pandas as pd

from pytorch_segmentation_models_trainer.utils.tensor_utils import tensor_dict_to_device

logger = logging.getLogger(__name__)

import os
import torch.distributed as dist
import torch.multiprocessing as mp

WORLD_SIZE = torch.cuda.device_count()


def instantiate_dataloaders(cfg):
    df = (
        pd.read_csv(
            cfg.inference_dataset.input_csv_path,
            nrows=cfg.inference_dataset.n_first_rows_to_read,
        )
        if "n_first_rows_to_read" in cfg.inference_dataset
        and cfg.inference_dataset.n_first_rows_to_read is not None
        else pd.read_csv(cfg.inference_dataset.input_csv_path)
    )
    ds_dict = ImageDataset.get_grouped_datasets(
        df,
        group_by_keys=["width", "height"],
        root_dir=cfg.inference_dataset.root_dir,
        augmentation_list=A.Compose([A.Normalize(), ToTensorV2()]),
    )
    batch_size = cfg.hyperparameters.batch_size
    return [
        torch.utils.data.DataLoader(
            ds,
            batch_size=batch_size,
            shuffle=False,
            drop_last=False,
            num_workers=cfg.inference_dataset.data_loader.num_workers,
            prefetch_factor=cfg.inference_dataset.data_loader.prefetch_factor,
        )
        for ds in ds_dict.values()
    ]


@hydra.main()
def predict_mod_polymapper_from_batch(cfg: DictConfig):
    logger.info(
        "Starting the prediction of a model with the following configuration: \n%s",
        OmegaConf.to_yaml(cfg),
    )
    model = import_module_from_cfg(cfg.pl_model).load_from_checkpoint(
        cfg.hyperparameters.resume_from_checkpoint, cfg=cfg
    )
    dataloader_list = instantiate_dataloaders(cfg)
    trainer = Trainer(**cfg.pl_trainer)
    for dataloader in tqdm(
        dataloader_list,
        total=len(dataloader_list),
        desc="Processing inference for each group of images",
        colour="green",
    ):
        trainer.predict(model, dataloader)


if __name__ == "__main__":
    predict_mod_polymapper_from_batch()
