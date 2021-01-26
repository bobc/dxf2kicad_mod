# ===========================================================================
# 
# Convert DXF file to KiCad footprint 
# 
# Derived from https://github.com/pandysong/dxf2kicad_mod
#
# ===========================================================================
#
# Copyright (C) 2018  pandy song
#
# Modifications  Copyright (c) 2018-2021 Bob Cousins 
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ===========================================================================
#
# This version has diverged a lot from the original. 
# - add support for more entity types
# - clean up arg parsing, debug output
# - unit conversion (mils)
# - use ezdxf instead of dxfgrabber
# - use semi-standard kicad-library-utils for writing KiCad footprint
#
# ===========================================================================

import argparse
import ezdxf
from ezdxf.math import Vec3
from math import *
import math
import sys
import os
import json
from enum import Enum

from kicad_layers import KicadLayer

common = os.path.abspath(os.path.join(sys.path[0], 'common'))
if not common in sys.path:
    sys.path.append(common)

from kicad_mod import *
from kicad_sym import *


class Units(Enum):
    MM = "mm"
    MIL = "mil"


class Point (object):
    x : float = 0
    y : float = 0
    bulge : float = 0

    def __init__ (self, x=0, y=0, pt=None):
        if type(pt) in [list, tuple]:
            self.x = pt[0]
            self.y = pt[1]

    def __str__ (self):
        return "{:6g}, {:6g}".format (self.x, self.y)


class Settings(object):
    # by default mm, will be converted to Mil if Mil selected

    def __init__(self, dct=None):
        if dct:
            self.units = dct.get('units', "mm")
            self.layers = dct.get('layer', {"0":KicadLayer.F_Cu} )
            self.distance_error = dct.get('distance_error', 0.1)
            self.min_line_width = dct.get('min_line_width', 0.2)
        else:
            self.units = "mm"
            self.layers = {"0":KicadLayer.F_Cu}
            self.distance_error = 0.025
            #self.distance_error = 0.1
            self.min_line_width = 0.2


    def save_to_file (cls, filename):
        json_data = json.dumps(cls, default=lambda o: o.__dict__, indent=4) 
        with open(filename, 'w') as file:
            file.write(json_data) 

    @classmethod
    def load_from_file (cls, filename):
        try:
            with open(filename, 'r') as file:
                json_data = file.read()
                return Settings(json.loads(json_data)) 
        except Exception as ex:
            print ("error reading settings file {} {}".format(filename, ex, file=sys.stderr))
            return Settings()

def debug_print (s):
    if args.verbose and args.verbose>1:
        print (s)

def verbose_print (s):
    if args.verbose and args.verbose>0:
        print (s)

def to_mil (val):
    return val * 1000 / 25.4

def to_mm (val):
    if settings.units == Units.MIL:
        return val * 0.0254
    return val

def pt_to_mm (pt):
    if settings.units == Units.MIL:
        return [pt[0] * 0.0254, pt[1] * 0.0254]
    return pt

#
def clip(subjectPolygon, clipPolygon):
    def inside(p):
        a = ( (cp1[0]-cp2[0]) * (p[1]-cp1[1]) ) - ( (cp1[1]-cp2[1]) * (p[0]-cp1[0]) )
        return a > 0

    def computeIntersection():
        dc = [ cp1[0] - cp2[0], cp1[1] - cp2[1] ]
        dp = [ s[0] - e[0], s[1] - e[1] ]
        n1 = cp1[0] * cp2[1] - cp1[1] * cp2[0]
        n2 = s[0] * e[1] - s[1] * e[0]
        n3 = 1.0 / (dc[0] * dp[1] - dc[1] * dp[0])

        p = [(n1*dp[0] - n2*dc[0]) * n3, (n1*dp[1] - n2*dc[1]) * n3]
        return p

    outputList = subjectPolygon
    cp1 = clipPolygon[-1]

    for clipVertex in clipPolygon:

        cp2 = clipVertex

        inputList = outputList
        outputList = []

        if len (inputList)==0:
            break

        s = inputList[-1]

        for subjectVertex in inputList:
            e = subjectVertex
            # print "v ", e
            if inside(e):
                if not inside(s):
                    outputList.append(computeIntersection())
                outputList.append(e)
            elif inside(s):
                outputList.append(computeIntersection())
            s = e
        cp1 = cp2

    return(outputList)

def distance_between_points (p1, p2):
    dx = math.fabs(p1[0] - p2[0])
    dy = math.fabs(p1[1] - p2[1])
    return math.sqrt (dx*dx + dy*dy)

#
def find_center(start, end, angle):

    dx = end[0] - start[0]
    dy = end[1] - start[1]

    mid = [(start[0] + dx / 2), (start[1] + dy / 2)]

    dlen = math.sqrt(dx * dx + dy * dy)
    dist = dlen / (2 * math.tan(angle / 2))

    center = [(mid[0] + dist * (dy / dlen)), (mid[1] - dist * (dx / dlen)) ]

    radius = math.sqrt(dist * dist + (dlen / 2) * (dlen / 2))

    arc_start = math.atan2(start[1] - center[1], start[0] - center[0])
    arc_end = math.atan2(end[1] - center[1], end[0] - center[0])

    return radius, center[0], center[1], arc_start, arc_end
#

#
def get_start_end_pts(entity):
    if "LINE" == entity.dxf.dxftype:
        start = get_point(entity.dxf.start)
        end = get_point(entity.dxf.end)
        debug_print("LINE {} {}".format(start, end))
        return (start, end)

    elif "ARC" == entity.dxf.dxftype:
        center = get_point (entity.dxf.center)
        start = (center[0] + entity.dxf.radius * math.cos(radians(entity.dxf.start_angle)),
              center[1] + entity.dxf.radius * math.sin(radians(entity.dxf.start_angle)), 0)
        end = (center[0] + entity.dxf.radius * math.cos(radians(entity.dxf.end_angle)),
            center[1] + entity.dxf.radius * math.sin(radians(entity.dxf.end_angle)), 0)
        debug_print("ARC {} {}".format(start, end))
        return (start,end)

    elif entity.dxf.dxftype in ["LWPOLYLINE", "POLYLINE"]:
        ety_points = get_points (entity)
        return (ety_points[0], ety_points[-1])

    else:
        print("[Error]: Unexpected dxftype {}".format(entity.dxf.dxftype), file=sys.stderr)


def is_poly (entity):
    if entity.dxf.dxftype in ['LWPOLYLINE', "POLYLINE"]:
        return True
    else:
        return False

def get_point (vec : Vec3):
    return [vec.x, vec.y]

def get_points (entity):
    if entity.dxf.dxftype == "LWPOLYLINE":
        points = []
        for pt in entity.get_points('xyb'):
            # pt is tuple (x,y,bulge)
            points.append (pt)
        return points

    elif entity.dxf.dxftype == "POLYLINE":
        points = []
        for pt in entity.vertices:
            # pt is VERTEX
            # pt.dxf.location is Vec3
            points.append ([pt.dxf.location.x, pt.dxf.location.y, pt.dxf.bulge])
        return points

    elif entity.dxf.dxftype == "LINE":
        return [ get_point(entity.dxf.start), get_point(entity.dxf.end) ]

    elif entity.dxf.dxftype == "ARC":
        center = get_point (entity.dxf.center)
        return [center]

    else:
        raise Exception ("entity {} has no points".format(entity))

def is_poly_closed (poly_points):
    dx = math.fabs(poly_points[0][0] - poly_points[-1][0])
    dy = math.fabs(poly_points[0][1] - poly_points[-1][1])
    if (dx < settings.distance_error) and (dy < settings.distance_error):
        return True
    else:
        return False

#
def add_points(ety, direction, cur_poly):

    points = []
    if 'LINE' == ety.dxf.dxftype:
        points = get_points (ety)

    elif 'ARC' == ety.dxf.dxftype:

        step = 1.0/ety.dxf.radius
        angle = ety.dxf.start_angle
        center = get_point(ety.dxf.center)

        debug_print ("angle {} {}".format( ety.dxf.start_angle, ety.dxf.end_angle))

        if (ety.dxf.start_angle > ety.dxf.end_angle):
            ety.dxf.end_angle += 360
        while True:
            points.append( (center[0] + ety.dxf.radius * math.cos(radians(angle)),
                            center[1] + ety.dxf.radius * math.sin(radians(angle))) )
            angle +=  step
            if (angle > ety.dxf.end_angle):
                break

    elif ety.dxf.dxftype in ["LWPOLYLINE", "POLYLINE"]:
        ety_points = get_points(ety)
        for j,point in enumerate(ety_points):
            #print ("{} {} ".format (j, point))
            if ety.dxf.dxftype == "LWPOLYLINE" and j == len(ety_points)-1:
                break

            #dbg ("%d %2.1f,%2.1f %2.3f" % (j, ety.points[j][0], ety.points[j][1], ety.bulge[j]))

            if point[2] == 0:
                points.append (point)
            else:
                if point[2] < 0:
                    p2 = ety_points[j]
                    p1 = ety_points[(j+1) % len(ety_points)]
                else:
                    p1 = ety_points[j]
                    p2 = ety_points[(j+1) % len(ety_points)]

                pl = []
                if p1[0] != p2[0] and p1[1] != p2[1]:
                    angle = math.atan(point[2]) * 4.0
                    radius, xc, yc, start_angle, end_angle = find_center(p1, p2, angle)
                    #dbg ("        r=%2.1f c=(%2.1f,%2.1f) sa=%2.1f ea=%2.1f" % (radius, xc, yc, degrees(start_angle), degrees(end_angle)))
                    if end_angle < start_angle:
                        end_angle += 2 * math.pi
                    angle = start_angle
                    step = math.radians(1.0/radius)
                    while 1:
                        pl.append( (xc + radius * math.cos(angle), yc + radius * math.sin(angle)) )
                        angle += step
                        if angle > max(start_angle, end_angle):
                            break
                    #
                    if start_angle < end_angle :
                        pl.reverse()
                    for p in pl:
                        points.append (p)

    else:
        print ("[Error]: Unexpected dxftype {}".format(entity.dxftype), file=sys.stderr)

    #
    if direction == -1:
        points.reverse()

    # don't add last point?
    for point in points:
        cur_poly.append (point)


def get_layer_name (layer):
    if layer in settings.layers:
        return settings.layers.get (layer, layer)
    elif layer in KicadLayer.standard_layers:
        return layer
    else:
        return KicadLayer.F_Cu

#

class DxfConverter:

    def __init__ (self, dxf):
        self.dxf = dxf
        self.footprint = None

    def add_poly (self, poly_points, width, layer):
        points = []
        for point in poly_points:
            # in KiCad Y axis has opposite direction
            pt_mm = pt_to_mm (point)
            points.append ({'x': round(pt_mm[0],4), 'y':round(-pt_mm[1],4)})
        poly = {'layer':get_layer_name(layer), 'width':to_mm(width), 'pts':points}

        self.footprint.polys.append (poly)

    # compatible with v5
    def add_lines (self, poly_points, width, layer):

        for j,point in enumerate(poly_points[:-1]):
            # in KiCad Y axis has opposite direction
            start = pt_to_mm( [point[0], -point[1]] )
            end = pt_to_mm ( [ poly_points [j + 1][0], -poly_points [j + 1][1] ] )
            self.footprint.addLine(start, end, get_layer_name(layer), to_mm(width) )

    # requires v6?
    def add_lines_v6 (self, poly_points, width, layer):
        points = []
        for point in poly_points:
            # in KiCad Y axis has opposite direction
            pt_mm = pt_to_mm (point)
            points.append ({'x': round(pt_mm[0],4), 'y':round(-pt_mm[1],4)})
        # width must be > 0
        poly = {'layer':get_layer_name(layer), 'width':0.001, 'pts':points, 'fill': 'none'}

        self.footprint.polys.append (poly)


    def is_near (self, p1, p2):
        dx = math.fabs(p1[0] - p2[0])
        dy = math.fabs(p1[1] - p2[1])
        if (dx < settings.distance_error) and (dy < settings.distance_error):
            return True
        else:
            return False
        

    def start_new_shape (self, layer):

        if self.cur_poly:
            #todo : width
            self.add_poly (self.cur_poly, 0, layer)

        self.cur_poly = []

        if len(self.not_processed_data) > 0:
            self.current_shape = self.not_processed_data.pop() #pick up one
            points = get_start_end_pts(self.current_shape)

            self.point_to_close = points[0]
            self.pts_next = points[1]

            debug_print ("starting point {}".format(self.point_to_close))

            add_points(self.current_shape, 1, self.cur_poly)
        else:
            self.pts_next = None


    def convert_layers (self, dxf, footprint_path):

        basename = os.path.splitext(os.path.basename(footprint_path))[0]

        self.footprint = KicadMod ()
        self.footprint.name = basename
        self.footprint.description = "Converted from " + os.path.basename(footprint_path)
        self.footprint.tags = "DXF"
        self.footprint.layer = KicadLayer.F_Cu
        self.footprint.attribute = 'virtual'
        self.footprint.reference['layer'] = KicadLayer.F_SilkScreen
        self.footprint.reference['hide'] = True
        self.footprint.reference['pos']['x'] = 0
        self.footprint.reference['pos']['y'] = -4
        self.footprint.reference['font']['thickness'] = 0.2
        self.footprint.value['layer'] = KicadLayer.F_SilkScreen
        self.footprint.value['hide'] = True
        self.footprint.value['pos']['x'] = 0
        self.footprint.value['pos']['y'] = 4
        self.footprint.value['font']['thickness'] = 0.2

        print ("Creating {}".format(basename))

        layers = [layer.dxf.name for layer in dxf.layers]
        debug_print ("Layers: {}".format(layers))

        self.cur_poly = []

        model_space = dxf.modelspace()

        # todo: get drawing extent

        for layer in layers:

            verbose_print ("layer {} to {}".format (layer, get_layer_name(layer)))

            self.layer_data = model_space.query ('*[layer =="{}"]'.format(layer))
            self.not_processed_data = []

            for entity in self.layer_data:
                if entity.dxf.dxftype in  ["LWPOLYLINE", "POLYLINE"]:

                    num_points = entity.__len__()
                    verbose_print ("poly {} {} {}".format(entity, num_points, entity.is_closed))

                    # todo: segments may have different widths
                    if entity.dxf.dxftype == "LWPOLYLINE":
                        num_points -= 1
                        width = entity.dxf.const_width
                    else:
                        width = entity.dxf.default_start_width
                    width = max(width, settings.min_line_width)
                    points = get_points(entity)

                    if num_points == 2:
                        #print ("simple poly")
                        #todo: handle bulge
                        start = points[0]
                        end   = points[1]
                        line = model_space.add_line (start, end)
                        line.dxf.thickness =  max(entity.dxf.default_start_width, settings.min_line_width)
                        self.not_processed_data.append (line)
                        debug_print ("added line {}".format(line.dxf.thickness))
                    else:
                        self.cur_poly = []
                        add_points(entity, 1, self.cur_poly)

                        if is_poly_closed (self.cur_poly):
                            self.add_poly (self.cur_poly, width, layer)
                        else:
                            if entity.is_closed:
                                self.cur_poly.append (self.cur_poly[0])
                                self.add_poly (self.cur_poly, width, layer)
                            else:
                                self.add_lines (self.cur_poly, width, layer)

                elif entity.dxf.dxftype in  ["ARC", "LINE"]:
                    self.not_processed_data.append (entity)
                    verbose_print ("added {}".format(entity))

                else:
                    verbose_print ("entity {} discarded".format(entity))

            #
            self.cur_poly = []
            self.start_new_shape(layer)
            debug_print ("Not Processed Shape: {}".format (len(self.not_processed_data)))

            while self.pts_next:

                if is_poly (self.current_shape):
                    debug_print ("cur is poly")
                    self.start_new_shape(layer)
                    continue
                #
                pt = self.pts_next
                debug_print ("Searching entity which is connected with {}".format(pt))
                #
                matched_entity = None
                nearest_pt = None
                nearest_dist = math.inf

                for entity in self.not_processed_data:
                    points = get_start_end_pts(entity)

                    d = distance_between_points (points[0], pt)
                    if d < nearest_dist:
                        nearest_dist = d
                        nearest_pt = points[0]

                    if self.is_near (points[0], pt):
                        # matched
                        matched_entity = entity
                        direction = 1 # from start to end
                        self.pts_next = points[1]
                        debug_print ("Got the Point {}".format(Point(pt=points[0])))
                        break

                    d = distance_between_points (points[1], pt)
                    if d < nearest_dist:
                        nearest_dist = d
                        nearest_pt = points[1]

                    if self.is_near (points[1], pt):
                        # matched
                        matched_entity = entity
                        direction = -1 # from end to start
                        self.pts_next = points[0]
                        debug_print ("Got the Point {}".format(Point(pt=points[1])))
                        break

                if matched_entity == None:

                    debug_print ("No match found, check if we could close the loop")

                    if self.is_near (self.point_to_close, pt):
                        debug_print ("shape closed at {}".format(pt))
                        self.cur_poly.append (pt)
                        # find next shape
                        self.start_new_shape(layer)
                        debug_print ("Not Processed Shape: {}".format(len(self.not_processed_data)))

                    else:
                        verbose_print ("unconnected line on layer {} at {} - nearest was {} {:.4f}".
                                       format (layer, Point(pt=self.pts_next), nearest_pt, nearest_dist))

                        self.add_lines (self.cur_poly, self.current_shape.dxf.thickness, layer)

                        self.cur_poly = []
                        self.start_new_shape(layer)
                else:
                    debug_print ("now print the line on {}".format(matched_entity))
                    add_points(matched_entity, direction, self.cur_poly)

                    debug_print ("removed from the set, {}".format(matched_entity))
                    self.not_processed_data.remove(matched_entity) #remove from the set

                    debug_print ("Not Processed Shape: {}".format (len(self.not_processed_data)))

        # write footprint
        self.footprint.save(footprint_path)


#
def dump_file (dxf):
    model_space = dxf.modelspace()
    layers = [layer.dxf.name for layer in dxf.layers]

    #print ("Layers: {}".format(layers))

    for layer in layers:
        print ("Layer: {}".format(layer))

        layer_data = model_space.query ('*[layer =="{}"]'.format(layer))

        for entity in layer_data:
            if entity.dxf.dxftype == "ARC":
                info = "{} {} {} {}".format (entity.dxf.center, entity.dxf.radius, entity.dxf.start_angle, entity.dxf.end_angle)
            elif entity.dxf.dxftype == "LINE":
                info = "{} {}".format(entity.dxf.start, entity.dxf.end)
            elif entity.dxf.dxftype == "INSERT":
                info = "{} {} {}".format(entity.dxf.name, entity.dxf.xscale, entity.dxf.yscale)
            elif entity.dxf.dxftype == "POLYLINE":
                info = "closed:{} np:{}".format (entity.is_closed, len(entity))
            elif entity.dxf.dxftype == "LWPOLYLINE":
                info = "closed:{} np:{}".format (entity.is_closed, len(entity))
            else:
                info = ''
            print ("  {} {}".format(entity, info))


if __name__ == '__main__':


    #settings = Settings.load_from_file ("settings.json")
    settings = Settings()
    #settings.save_to_file("settings.json")

    #
    parser = argparse.ArgumentParser(description='Convert a DXF file to a KiCad footprint')
    parser.add_argument('DXF_file', help="DXF file")
    parser.add_argument('footprint_file', help="KiCad footprint file name", nargs='?')
    parser.add_argument('-v', '--verbose', help='Enable verbose output. -v shows brief information, -vv shows complete information', action='count')
    parser.add_argument('-d', '--dump', help='Dump the DXF file.', action='store_true')
    parser.add_argument('-u', '--units', help='File units: MM or MIL.', default="mm")
    args = parser.parse_args()

    if os.path.splitext(args.DXF_file)[1].lower() == ".dxf":

        if args.units.lower() == Units.MIL:
            settings.units = Units.MIL
            settings.distance_error = to_mil (settings.distance_error)
            settings.min_line_width = to_mil (settings.min_line_width)

        dxf = ezdxf.readfile(args.DXF_file)

        debug_print ("DXF version : {}".format(dxf.dxfversion))
        debug_print ("Entity Count: {}".format (len(dxf.entities)))

        if args.dump:
            dump_file(dxf)
        else:
            if args.footprint_file:
                out_file = args.footprint_file
            else:
                out_file = os.path.basename(args.DXF_file)
                out_file = os.path.splitext(out_file)[0] + ".kicad_mod"

            converter = DxfConverter(dxf)
            converter.convert_layers(dxf, out_file)
