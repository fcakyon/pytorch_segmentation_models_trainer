# -*- coding: utf-8 -*-
"""
/***************************************************************************
 pytorch_segmentation_models_trainer
                              -------------------
        begin                : 2021-03-09
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
import logging
from pathlib import Path
import albumentations as A
import pytorch_lightning as pl
import torch
from hydra.utils import instantiate

# precision e recall com problema no pytorch lightning 1.2,
# retirar e depois ver o que fazer
from torch.utils.data import DataLoader

from typing import List, Any

import concurrent.futures

from pytorch_segmentation_models_trainer.predict import instantiate_polygonizer
from concurrent.futures import Future

logger = logging.getLogger(__name__)


class WarmupCallback(pl.callbacks.base.Callback):
    def __init__(self, warmup_epochs=2) -> None:
        super().__init__()
        self.warmup_epochs = warmup_epochs
        self.warmed_up = False

    def on_init_end(self, trainer):
        print(f"\nWarmupCallback initialization at epoch {trainer.current_epoch}.\n")
        if trainer.current_epoch > self.warmup_epochs - 1:
            self.warmed_up = True

    def on_train_epoch_start(self, trainer, pl_module):
        if self.warmed_up or trainer.current_epoch < self.warmup_epochs - 1:
            return
        if not self.warmed_up:
            print(
                f"\nModel will warm up for {self.warmup_epochs} "
                "epochs. Freezing encoder weights.\n"
            )
            self.set_component_trainable(pl_module, trainable=False)

    def on_train_epoch_end(self, trainer, pl_module):
        if self.warmed_up:
            return
        if trainer.current_epoch >= self.warmup_epochs - 1:
            print(
                f"\nModel warm up completed in the end of epoch {trainer.current_epoch}. "
                "Unfreezing encoder weights.\n"
            )
            self.set_component_trainable(pl_module, trainable=True)
            self.warmed_up = True

    def set_component_trainable(self, pl_module, trainable=True):
        pl_module.set_encoder_trainable(trainable=trainable)


class FrameFieldOnlyCrossfieldWarmupCallback(pl.callbacks.base.Callback):
    def __init__(self, warmup_epochs=2) -> None:
        super().__init__()
        self.warmup_epochs = warmup_epochs
        self.warmed_up = False

    def on_init_end(self, trainer):
        print(
            f"\nFrameFieldWarmupCallback initialization at epoch {trainer.current_epoch}.\n"
        )
        if trainer.current_epoch > self.warmup_epochs - 1:
            self.warmed_up = True

    def on_train_epoch_start(self, trainer, pl_module):
        if self.warmed_up or trainer.current_epoch < self.warmup_epochs - 1:
            return
        if not self.warmed_up:
            print(
                f"\nFrame field model will warm up for {self.warmup_epochs} "
                "epochs. Freezing all weights but crossfield's.\n"
            )
            self.set_component_trainable(pl_module, trainable=False)

    def on_train_epoch_end(self, trainer, pl_module):
        if self.warmed_up:
            return
        if trainer.current_epoch >= self.warmup_epochs - 1:
            print(
                f"\nModel warm up completed in the end of epoch {trainer.current_epoch}. "
                "Unfreezing weights.\n"
            )
            self.set_component_trainable(pl_module, trainable=True)
            self.warmed_up = True

    def set_component_trainable(self, pl_module, trainable=True):
        pl_module.set_all_but_crossfield_trainable(trainable=trainable)


class FrameFieldComputeWeightNormLossesCallback(pl.callbacks.base.Callback):
    def __init__(self) -> None:
        super().__init__()
        self.loss_norm_is_initializated = False

    def on_train_epoch_start(self, trainer, pl_module) -> None:
        if self.loss_norm_is_initializated or trainer.current_epoch > 1:
            return
        pl_module.model.train()  # Important for batchnorm and dropout, even in computing loss norms
        init_dl = pl_module.train_dataloader()
        with torch.no_grad():
            loss_norm_batches_min = (
                pl_module.cfg.loss_params.multiloss.normalization_params.min_samples
                // (2 * pl_module.cfg.hyperparameters.batch_size)
                + 1
            )
            loss_norm_batches_max = (
                pl_module.cfg.loss_params.multiloss.normalization_params.max_samples
                // (2 * pl_module.cfg.hyperparameters.batch_size)
                + 1
            )
            loss_norm_batches = max(
                loss_norm_batches_min, min(loss_norm_batches_max, len(init_dl))
            )
            pl_module.compute_loss_norms(init_dl, loss_norm_batches)
        self.loss_norm_is_initializated = True


class FrameFieldPolygonizerCallback(pl.callbacks.BasePredictionWriter):
    def __init__(self) -> None:
        super().__init__()

    def on_predict_batch_end(
        self, trainer, pl_module, outputs, batch, batch_idx, dataloader_idx
    ):
        parent_dir_name_list = [Path(path).stem for path in batch["path"]]
        seg_batch, crossfield_batch = outputs
        if seg_batch is None and crossfield_batch is None:
            return
        with concurrent.futures.ThreadPoolExecutor() as pool:
            polygonizer = instantiate_polygonizer(pl_module.cfg)
            try:
                with torch.enable_grad():
                    futures = polygonizer.process(
                        {"seg": seg_batch, "crossfield": crossfield_batch},
                        profile=None,
                        parent_dir_name=parent_dir_name_list,
                        pool=None,
                        convert_output_to_world_coords=False,
                    )
            except Exception as e:
                logger.error(f"Error in polygonizer: {e}")
                logger.warning(
                    "Skipping polygonizer for batch with error. Check it later."
                )
            if (
                isinstance(futures, list)
                and len(futures) > 0
                and isinstance(futures[0], Future)
            ):
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error in polygonizer: {e}")
                        logger.warning(
                            "Skipping polygonizer for batch with error. Check it later."
                        )
        del seg_batch, crossfield_batch, parent_dir_name_list
