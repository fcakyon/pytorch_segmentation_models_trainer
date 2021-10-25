# -*- coding: utf-8 -*-
"""
/***************************************************************************
 pytorch_segmentation_models_trainer
                              -------------------
        begin                : 2021-08-03
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
 *   Part of the code is from                                              *
 *   https://github.com/AlexMa011/pytorch-polygon-rnn                      *
 ****
"""

from typing import List
from PIL import Image, ImageDraw
import numpy as np
import torch


def label2vertex(labels):
    """
    convert 1D labels to 2D vertices coordinates
    :param labels: 1D labels
    :return: 2D vertices coordinates: [(x1, y1),(x2,y2),...]
    """
    vertices = []
    for label in labels:
        if label == 784:
            break
        vertex = ((label % 28) * 8, (label / 28) * 8)
        vertices.append(vertex)
    return vertices


def get_vertex_list(input_list: List[float]) -> List[float]:
    vertex_list = []
    for label in input_list:
        if label == 784:
            break
        vertex = ((label % 28) * 8.0 + 4, (int(label / 28)) * 8.0 + 4)
        vertex_list.append(vertex)
    return vertex_list


def getbboxfromkps(kps, h, w):
    """

    :param kps:
    :return:
    """
    min_c = np.min(np.array(kps), axis=0)
    max_c = np.max(np.array(kps), axis=0)
    object_h = max_c[1] - min_c[1]
    object_w = max_c[0] - min_c[0]
    h_extend = int(round(0.1 * object_h))
    w_extend = int(round(0.1 * object_w))
    min_row = np.maximum(0, min_c[1] - h_extend)
    min_col = np.maximum(0, min_c[0] - w_extend)
    max_row = np.minimum(h, max_c[1] + h_extend)
    max_col = np.minimum(w, max_c[0] + w_extend)
    return (min_row, min_col, max_row, max_col)


def img2tensor(img):
    """

    :param img:
    :return:
    """
    img = np.rollaxis(img, 2, 0)
    return torch.from_numpy(img)


def tensor2img(tensor):
    """

    :param tensor:
    :return:
    """
    img = (tensor.numpy() * 255).astype("uint8")
    img = np.rollaxis(img, 0, 3)
    return img


def build_arrays(polygon, num_vertexes, sequence_length):
    point_count = 2
    label_array = np.zeros([sequence_length, 28 * 28 + 3])
    label_index_array = np.zeros([sequence_length])
    if num_vertexes < sequence_length - 3:
        for points in polygon:
            _initialize_label_index_array(
                point_count, label_array, label_index_array, points
            )
            point_count += 1
        _populate_label_index_array(
            polygon,
            num_vertexes,
            sequence_length,
            point_count,
            label_array,
            label_index_array,
        )
    else:
        scale = num_vertexes * 1.0 / (sequence_length - 3)
        index_list = (np.arange(0, sequence_length - 3) * scale).astype(int)
        for points in polygon[index_list]:
            _initialize_label_index_array(
                point_count, label_array, label_index_array, points
            )
            point_count += 1
        for kkk in range(point_count, sequence_length):
            index = 28 * 28
            label_array[kkk, index] = 1
            label_index_array[kkk] = index
    return label_array, label_index_array


def _populate_label_index_array(
    polygon, num_vertexes, sequence_length, point_count, label_array, label_index_array
):
    label_array[point_count, 28 * 28] = 1
    label_index_array[point_count] = 28 * 28
    for kkk in range(point_count + 1, sequence_length):
        if kkk % (num_vertexes + 3) == num_vertexes + 2:
            index = 28 * 28
        elif kkk % (num_vertexes + 3) == 0:
            index = 28 * 28 + 1
        elif kkk % (num_vertexes + 3) == 1:
            index = 28 * 28 + 2
        else:
            index_a = int(polygon[kkk % (num_vertexes + 3) - 2][0] / 8)
            index_b = int(polygon[kkk % (num_vertexes + 3) - 2][1] / 8)
            index = index_b * 28 + index_a
        label_array[kkk, index] = 1
        label_index_array[kkk] = index


def _initialize_label_index_array(point_count, label_array, label_index_array, points):
    index_a = int(points[0] / 8)
    index_b = int(points[1] / 8)
    index = index_b * 28 + index_a
    label_array[point_count, index] = 1
    label_index_array[point_count] = index
