import collections
import os

import cv2
import numpy as np
import networkx as nx

import dataset


DOC_FNAME = 'doc.png'
SHRED_MASK_FNAME = 'mask.png'


# Right, bottom are offsets of the next shred.
ShredConfig = collections.namedtuple("ShredConfig", "mask right bottom")


def load_targets():
    """Loads the source data for trying out a classifier.

    Returns:
        A 2-tuple of (doc image, shred_config). doc image is a 2d numpy array
        with white foreground on black background. shred_config is a ShredConfig
        instance.
    """
    raw = cv2.imread(os.path.join(dataset.DATADIR,DOC_FNAME))

    doc = 255 - cv2.cvtColor(raw, cv2.cv.CV_BGR2GRAY)
    mask = cv2.cvtColor(
            cv2.imread(
                os.path.join(dataset.DATADIR, SHRED_MASK_FNAME)),
            cv2.cv.CV_BGR2GRAY)

    shred_config = ShredConfig(mask=mask,
                               right=np.array((100, 110)),
                               bottom=np.array((550, 0)))
    return doc, shred_config


def cut_to_shreds(size, shred_config):
    """Builds an adjacency graph of shreds for a document of the given size.

    Args:
        size: 2-tuple of target doc image size.
        shred_config: A ShredConfig instance with shred parameters.
    Returns:
        nx.Graph instance with nodes - shred coordinates.
    """
    graph = nx.Graph()

    done = set()
    todo = {(0, 0)}

    while todo:
        base_point = todo.pop()
        done.add(base_point)

        base_point = np.array(base_point)

        slice_ind = dataset.to_slice(base_point, shred_config.mask.shape)

        neighbors = [
            base_point - shred_config.right,  # left
            base_point + shred_config.right,  # right
            base_point - shred_config.bottom,  # top
            base_point + shred_config.bottom,  # bottom
        ]

        graph.add_node(tuple(base_point), slice=slice_ind)

        for neighbor in neighbors:
            if (any(neighbor < 0) or
                any(neighbor+shred_config.mask.shape > size)):
                    continue

            graph.add_edge(tuple(base_point), tuple(neighbor))

            if (tuple(neighbor) in done or
                tuple(neighbor) in todo):
                continue

            todo.add(tuple(neighbor))

    return graph


def is_good_node(img):
    num_non_zeros = np.count_nonzero(img)
    return (float(num_non_zeros) / img.size) > 0.05


def masked_shred(shred, mask):
    masked_slice = shred.copy()
    masked_slice = cv2.bitwise_and(masked_slice, masked_slice, mask=mask)
    return masked_slice


def real_distance(key1, key2, edges):
    return 0 if (key1 in edges and key2 in edges[key1]) else 1

def preserve_outermost(image, foreground_mask):
  """Only leaves foreground image components adjacent to the border.

  Args:
    image: 2D numpy array with white foreground and black background.
    foreground_mask: mask with white where the image foreground is.

  Returns:
    2D array like image but with only foreground components adjacent to
        "outside" preserved.
  """
  # Leave the values [0, 254] to the outside.
  outside_mask = cv2.threshold(foreground_mask, 254, 255,
                               cv2.THRESH_BINARY_INV)[1]
  with_outside = np.maximum(image, outside_mask)

  flood_fill_mask = 255 - dataset.pad_image(with_outside, 1)

  # Some point outside the foreground mask.
  seed_point = np.argwhere(outside_mask == 255)[0]

  # Unused flood fil value.
  new_val = 128

  # flood_fill_mask is set to 1, where the flood fill was applied.
  cv2.floodFill(with_outside, flood_fill_mask, tuple(seed_point[::-1]), new_val)

  return cv2.bitwise_and(
      image, image, mask=(flood_fill_mask == 1).astype(np.uint8)[1:-1, 1:-1])
