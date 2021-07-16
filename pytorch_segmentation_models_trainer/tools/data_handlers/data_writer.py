# -*- coding: utf-8 -*-
"""
/***************************************************************************
 pytorch_segmentation_models_trainer
                              -------------------
        begin                : 2021-07-14
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
from copy import deepcopy
from typing import List, Union
import numpy as np
import os
import shapely
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from geopandas import GeoDataFrame, GeoSeries
from omegaconf import MISSING
import rasterio
from rasterio.plot import reshape_as_raster
from sqlalchemy.engine import create_engine
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry

class AbstractDataWriter(ABC):
    @abstractmethod
    def write_data(self, input_data: np.array) -> None:
        pass

@dataclass
class RasterDataWriter(AbstractDataWriter):
    output_file_path: str = MISSING
    profile: dict = field(default_factory=dict)

    def write_data(self, input_data: np.array) -> None:
        profile = deepcopy(self.profile)
        profile['count'] = input_data.shape[-1]
        with rasterio.open(self.output_file_path, 'w', **profile) as out:
            out.write(reshape_as_raster(input_data))

@dataclass
class VectorFileDataWriter(AbstractDataWriter):
    output_file_path: str = MISSING
    crs: str = MISSING
    driver: str = "GeoJSON"

    def write_data(self, input_data: List[Union[BaseGeometry, BaseMultipartGeometry]]) -> None:
        geoseries = GeoSeries(input_data, crs=self.crs)
        gdf = GeoDataFrame.from_features(geoseries, crs=self.crs)
        gdf.to_file(
            self.output_file_path,
            driver=self.driver
        )

@dataclass
class VectorDatabaseDataWriter(AbstractDataWriter):
    user: str = MISSING
    password: str = MISSING
    database: str = MISSING
    sql: str = MISSING
    crs: str = MISSING
    host: str = "localhost"
    port: int = 5432
    table_name: str = "buildings"
    geometry_column: str = "geom"
    if_exists: str = "append"

    def write_data(self, input_data: List[Union[BaseGeometry, BaseMultipartGeometry]]) -> None:
        geoseries = GeoSeries(input_data, crs=self.crs)
        gdf = GeoDataFrame.from_features(geoseries, crs=self.crs)
        gdf.rename_geometry(self.geometry_column, inplace=True)
        engine = create_engine(f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}")
        gdf.to_postgis(self.table_name, engine, if_exists=self.if_exists)