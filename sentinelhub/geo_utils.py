"""
Module for manipulation of geographical information.
"""

import logging
import pyproj

from .constants import CRS
from .common import BBox


LOGGER = logging.getLogger(__name__)

ERR = 0.1


def bbox_to_resolution(bbox, width, height):
    """ Calculates pixel resolution in meters for a given bbox of a given width and height.

    :param bbox: bounding box
    :type bbox: common.BBox
    :param width: width of bounding box in pixels
    :type width: int
    :param height: height of bounding box in pixels
    :type height: int
    :return: resolution east-west at north and south, and resolution north-south in meters for given CRS
    :rtype: float, float, float
    :raises: ValueError if CRS is not supported
    """
    utm_bbox = to_utm_bbox(bbox)
    east1, north1 = utm_bbox.get_lower_left()
    east2, north2 = utm_bbox.get_upper_right()
    return abs(east2 - east1) / width, abs(north2 - north1) / height


def get_image_dimension(bbox, width=None, height=None):
    """ Given bounding box and one of the parameters width or height it will return the other parameter that will best
    fit the bounding box dimensions

    :param bbox: bounding box
    :type bbox: common.BBox
    :param width: image width or None if height is unknown
    :type width: int or None
    :param height: image height or None if height is unknown
    :type height: int or None
    :return: width or height rounded to integer
    :rtype: int
    """
    utm_bbox = to_utm_bbox(bbox)
    east1, north1 = utm_bbox.get_lower_left()
    east2, north2 = utm_bbox.get_upper_right()
    if isinstance(width, int):
        return round(width * abs(north2 - north1) / abs(east2 - east1))
    return round(height * abs(east2 - east1) / abs(north2 - north1))


def to_utm_bbox(bbox):
    """ Transform bbox into UTM CRS

    :param bbox: bounding box
    :type bbox: common.BBox
    :return: bounding box in UTM CRS
    :rtype: common.BBox
    """
    if CRS.is_utm(bbox.get_crs()):
        return bbox
    lng, lat = bbox.get_middle()
    utm_crs = get_utm_crs(lng, lat, source_crs=bbox.get_crs())
    return transform_bbox(bbox, utm_crs)


def get_utm_bbox(img_bbox, transform):
    """ Get UTM coordinates given a bounding box in pixels and a transform

    :param img_bbox: boundaries of bounding box in pixels as [row1, col1, row2, col2]
    :type img_bbox: list
    :param transform: georeferencing transform of the image, e.g. (x_upper_left, res_x, 0, y_upper_left, 0, -res_y)
    :type transform: tuple or list
    :return: UTM coordinates as [east1, north1, east2, north2]
    :rtype: list
    """
    east1, north1 = pixel_to_utm(img_bbox[0], img_bbox[1], transform)
    east2, north2 = pixel_to_utm(img_bbox[2], img_bbox[3], transform)
    return [east1, north1, east2, north2]


def wgs84_to_utm(lng, lat, utm_crs=None):
    """ Convert WGS84 coordinates to UTM. If UTM CRS is not set it will be calculated automatically.

    :param lng: longitude in WGS84 system
    :type lng: float
    :param lat: latitude in WGS84 system
    :type lat: float
    :param utm_crs: UTM coordinate reference system enum constants
    :type utm_crs: constants.CRS or None
    :return: east, north coordinates in UTM system
    :rtype: float, float
    """
    if utm_crs is None:
        utm_crs = get_utm_crs(lng, lat)
    return transform_point((lng, lat), CRS.WGS84, utm_crs)


def to_wgs84(east, north, crs):
    """ Convert any CRS with (east, north) coordinates to WGS84

    :param east: east coordinate
    :type east: float
    :param north: north coordinate
    :type north: float
    :param crs: CRS enum constants
    :type crs: constants.CRS
    :return: latitude and longitude coordinates in WGS84 system
    :rtype: float, float
    """
    return transform_point((east, north), crs, CRS.WGS84)


def utm_to_pixel(east, north, transform, truncate=True):
    """ Convert UTM coordinate to image coordinate given a transform

    :param east: east coordinate of point
    :type east: float
    :param north: north coordinate of point
    :type north: float
    :param transform: georeferencing transform of the image, e.g. (x_upper_left, res_x, 0, y_upper_left, 0, -res_y)
    :type transform: tuple or list
    :param truncate: Whether to truncate pixel coordinates. Default is ``True``
    :type truncate: bool
    :return: row and column pixel image coordinates
    :rtype: float, float or int, int
    """
    column = (east - transform[0]) / transform[1]
    row = (north - transform[3]) / transform[5]
    if truncate:
        return int(row + ERR), int(column + ERR)
    return row, column


def pixel_to_utm(row, column, transform):
    """ Convert pixel coordinate to UTM coordinate given a transform

    :param row: row pixel coordinate
    :type row: int or float
    :param column: column pixel coordinate
    :type column: int or float
    :param transform: georeferencing transform of the image, e.g. (x_upper_left, res_x, 0, y_upper_left, 0, -res_y)
    :type transform: tuple or list
    :return: east, north UTM coordinates
    :rtype: float, float
    """
    east = transform[0] + column * transform[1]
    north = transform[3] + row * transform[5]
    return east, north


def wgs84_to_pixel(lng, lat, transform, utm_epsg=None, truncate=True):
    """ Convert WGS84 coordinates to pixel image coordinates given transform and UTM CRS. If no CRS is given it will be
    calculated it automatically.

    :param lng: longitude of point
    :type lng: float
    :param lat: latitude of point
    :type lat: float
    :param transform: georeferencing transform of the image, e.g. (x_upper_left, res_x, 0, y_upper_left, 0, -res_y)
    :type transform: tuple or list
    :param utm_epsg: UTM coordinate reference system enum constants
    :type utm_epsg: constants.CRS or None
    :param truncate: Whether to truncate pixel coordinates. Default is ``True``
    :type truncate: bool
    :return: row and column pixel image coordinates
    :rtype: float, float or int, int
    """
    east, north = wgs84_to_utm(lng, lat, utm_epsg)
    row, column = utm_to_pixel(east, north, transform, truncate=truncate)
    return row, column


def get_utm_crs(lng, lat, source_crs=CRS.WGS84):
    """ Get CRS for UTM zone in which (lat, lng) is contained.

    :param lng: longitude
    :type lng: float
    :param lat: latitude
    :type lat: float
    :param source_crs: source CRS
    :type source_crs: constants.CRS
    :return: CRS of the zone containing the lat,lon point
    :rtype: constants.CRS
    """
    if source_crs is not CRS.WGS84:
        lng, lat = transform_point((lng, lat), source_crs, CRS.WGS84)
    return CRS.get_utm_from_wgs84(lng, lat)


def transform_point(point, source_crs, target_crs):
    """ Maps point form src_crs to tgt_crs

    :param point: a tuple (x, y)
    :type point: (float, float)
    :param source_crs: source CRS
    :type source_crs: constants.CRS
    :param target_crs: target CRS
    :type target_crs: constants.CRS
    :return: point in target CRS
    :rtype: (float, float)
    """
    if source_crs == target_crs:
        return point
    old_x, old_y = point
    new_x, new_y = pyproj.transform(CRS.projection(source_crs), CRS.projection(target_crs), old_x, old_y)
    return new_x, new_y


def transform_bbox(bbox, target_crs):
    """ Maps bbox from current crs to target_crs

    :param bbox: bounding box
    :type bbox: common.BBox
    :param target_crs: target CRS
    :type target_crs: constants.CRS
    :return: bounding box in target CRS
    :rtype: common.BBox
    """
    source_crs = bbox.get_crs()
    lower_left = bbox.get_lower_left()
    upper_right = bbox.get_upper_right()
    new_lower_left = transform_point(lower_left, source_crs, target_crs)
    new_upper_right = transform_point(upper_right, source_crs, target_crs)
    return BBox((new_lower_left, new_upper_right), target_crs)
