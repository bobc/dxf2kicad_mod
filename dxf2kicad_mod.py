# refer to http://pythonhosted.org/dxfgrabber/
#
# Note that there must not be any line or shape overlapped

# Add support for LWPOLYLINE
# Bob Cousins 2018-02

import argparse
import dxfgrabber
import dxfgrabber.dxfentities
from math import *
import math
import sys
import os
from enum import Enum

common = os.path.abspath(os.path.join(sys.path[0], 'common'))
if not common in sys.path:
    sys.path.append(common)

from kicad_mod import *
from kicad_sym import *


class Units(Enum):
    MM = 0
    MIL = 1

# by default mm, will be converted to Mil if Mil selected
distance_error = 0.025
min_line_width = 0.2
g_units = Units.MM

def debug_print (s):
    if args.verbose and args.verbose>1:
        print (s)

def verbose_print (s):
    if args.verbose and args.verbose>0:
        print (s)

def to_mil (val):
    return val * 1000 / 25.4

def to_mm (val):
    if g_units == Units.MIL:
        return val * 0.0254
    return val

def pt_to_mm (pt):
    if g_units == Units.MIL:
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
    if "LINE" == entity.dxftype:
        debug_print("LINE {} {}".format(entity.start, entity.end))
        return (entity.start, entity.end)

    elif "ARC" == entity.dxftype:
        start = (entity.center[0] + entity.radius * math.cos(radians(entity.start_angle)),
              entity.center[1] + entity.radius * math.sin(radians(entity.start_angle)), 0)
        end = (entity.center[0] + entity.radius * math.cos(radians(entity.end_angle)),
            entity.center[1] + entity.radius * math.sin(radians(entity.end_angle)), 0)
        debug_print("ARC {} {}".format(start, end))
        return (start,end)

    elif entity.dxftype in ["LWPOLYLINE", "POLYLINE"]:
        return (entity.points[0], entity.points[-1])

    else:
        print("[Error]: Unexpected dxftype {}".format(entity.dxftype), file=sys.stderr)


def is_poly (entity):
    if entity.dxftype in ['LWPOLYLINE', "POLYLINE"]:
        return True
    else:
        return False

def is_poly_closed (poly_points):
    xd = math.fabs(poly_points[0][0] - poly_points[-1][0])
    yd = math.fabs(poly_points[0][1] - poly_points[-1][1])
    if (xd < distance_error) and (yd < distance_error):
        return True
    else:
        return False

#
def add_points(ety, direction, cur_poly):

    points = []
    if 'LINE' == ety.dxftype:
        points = [ety.start, ety.end]

    elif 'ARC' == ety.dxftype:

        step = 1.0/ety.radius
        angle = ety.start_angle

        debug_print ("angle {} {}".format( ety.start_angle, ety.end_angle))

        if (ety.start_angle > ety.end_angle):
            ety.end_angle += 360
        while True:
            points.append( (ety.center[0] + ety.radius * math.cos(radians(angle)),
                            ety.center[1] + ety.radius * math.sin(radians(angle))) )
            angle +=  step

            if (angle > ety.end_angle):
                break

    elif ety.dxftype in ["LWPOLYLINE", "POLYLINE"]:
        for j,point in enumerate(ety.points):

            #print ("{} {} ".format (j, point))

            if ety.dxftype == "LWPOLYLINE" and j == len(ety.points)-1:
                break

            #dbg ("%d %2.1f,%2.1f %2.3f" % (j, ety.points[j][0], ety.points[j][1], ety.bulge[j]))

            if ety.bulge[j] == 0:
                points.append (point)
            else:
                if ety.bulge[j] < 0:
                    p2 = ety.points[j]
                    p1 = ety.points[(j+1) % len(ety.points)]
                else:
                    p1 = ety.points[j]
                    p2 = ety.points[(j+1) % len(ety.points)]

                pl = []
                if p1[0] != p2[0] and p1[1] != p2[1]:
                    angle = math.atan(ety.bulge[j]) * 4.0
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
    if layer=="0":
        return "F.Cu"
    else:
        return layer
#

class DxfConverter:

    def __init__ (self, dxf):
        self.dxf = dxf
        self.distance_error = distance_error
        self.footprint = None

    def add_poly (self, poly_points, width, layer):
        points = []
        for point in poly_points:
            #in KiCad Y axis has opposite direction
            pt_mm = pt_to_mm (point)
            points.append ({'x': round(pt_mm[0],4), 'y':round(-pt_mm[1],4)})
        poly = {'layer':get_layer_name(layer), 'width':to_mm(width), 'pts':points}

        self.footprint.polys.append (poly)

    def add_lines (self, poly_points, width, layer):

        for j,point in enumerate(poly_points[:-1]):
            #in KiCad Y axis has opposite direction
            start = pt_to_mm( [point[0], -point[1]] )
            end = pt_to_mm ( [ poly_points [j + 1][0], -poly_points [j + 1][1] ] )
            self.footprint.addLine(start, end, get_layer_name(layer), to_mm(width) )


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
        self.footprint.description = "x"
        self.footprint.tags = "x"
        self.footprint.layer = 'F.Cu'
        self.footprint.reference['layer'] = 'F.SilkS'
        self.footprint.reference['hide'] = True
        self.footprint.reference['pos']['x'] = 0
        self.footprint.reference['pos']['y'] = -4
        self.footprint.reference['font']['thickness'] = 0.2
        self.footprint.value['layer'] = 'F.SilkS'
        self.footprint.value['hide'] = True
        self.footprint.value['pos']['x'] = 0
        self.footprint.value['pos']['y'] = 4
        self.footprint.value['font']['thickness'] = 0.2

        print ("Creating {}".format(basename))

        layers = set([entity.layer for entity in dxf.entities])
        debug_print ("Layers: {}".format(layers))

        self.cur_poly = []

        # todo: get drawing extent

        for layer in layers:

            #self.not_processed_data = set([entity for entity in dxf.entities if entity.layer == layer])
            self.layer_data = [entity for entity in dxf.entities if entity.layer == layer]

            self.not_processed_data = []

            for entity in self.layer_data:
                if entity.dxftype in  ["LWPOLYLINE", "POLYLINE"]:

                    verbose_print ("poly {} {} {}".format(entity, len(entity.points), entity.is_closed))
                    num_points = len(entity.points)

                    # todo: segments may have different widths
                    if entity.dxftype == "LWPOLYLINE":
                        num_points -= 1
                        width = entity.const_width
                    else:
                        width = entity.default_start_width
                    width = max(width, min_line_width)

                    if num_points == 2:
                        #print ("simple poly")
                        #todo: handle bulge
                        line = dxfgrabber.dxfentities.Line ()
                        line.dxftype = 'LINE'
                        line.start = entity.points[0]
                        line.end = entity.points[1]
                        line.thickness =  max(entity.default_start_width, min_line_width)
                        self.not_processed_data.append (line)
                        debug_print ("added line {}".format(line.thickness))
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

                elif entity.dxftype in  ["ARC", "LINE"]:
                    self.not_processed_data.append (entity)
                    verbose_print ("added {}".format(entity))

                else:
                    verbose_print ("entity {} discarded".format(entity))

            #
            self.cur_poly = []
            self.start_new_shape(layer)
            debug_print ("Not Processed Shape: {}".format (len(self.not_processed_data)))

            while True:

                if self.pts_next == None:
                    debug_print("pts_next is None")
                    break #stop

                if is_poly (self.current_shape):
                    debug_print ("cur is poly")
                    self.start_new_shape(layer)
                    continue
                #
                pt = self.pts_next
                debug_print ("Searching entity which is connected with {}".format(pt))
                #
                matched_entity = None

                for entity in self.not_processed_data:
                    points = get_start_end_pts(entity)
                    x = points[0][0]
                    y = points[0][1]
                    if (math.fabs(x-pt[0]) < self.distance_error) and (math.fabs(y-pt[1]) < self.distance_error):
                        #matched
                        matched_entity = entity
                        direction = 1 #from start to end
                        self.pts_next = points[1]
                        debug_print ("Got the Point {} {}".format(x, y))
                        break

                    x = points[1][0]
                    y = points[1][1]
                    if (math.fabs(x-pt[0]) < self.distance_error) and (math.fabs(y-pt[1]) < self.distance_error):
                        #matched
                        matched_entity = entity
                        direction = -1 #from end to start
                        self.pts_next = points[0]
                        debug_print ("Got the Point {} {}".format(x, y))
                        break

                if matched_entity == None:

                    debug_print ("No match found, check if we could close the loop")

                    if ( (math.fabs(self.point_to_close[0]-pt[0]) < self.distance_error) and
                         (math.fabs(self.point_to_close[1]-pt[1]) < self.distance_error) ):
                        debug_print ("shape closed at {}".format(pt))
                        self.cur_poly.append (pt)
                        #find next shape
                        self.start_new_shape(layer)
                        debug_print ("Not Processed Shape: {}".format(len(self.not_processed_data)))
                    else:
                        verbose_print ("unconnected line on layer {}".format (layer))
                        self.add_lines (self.cur_poly, self.current_shape.thickness, layer)

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
    layers = set([entity.layer for entity in dxf.entities])

    #print ("Layers: {}".format(layers))

    for layer in layers:

        print ("Layers: {}".format(layer))

        layer_data = set([entity for entity in dxf.entities if entity.layer == layer])

        for entity in layer_data:
            if entity.dxftype == "ARC":
                info = "{} {} {} {}".format (entity.center, entity.radius, entity.start_angle, entity.end_angle)
            elif entity.dxftype == "LINE":
                info = "{} {}".format(entity.start, entity.end)
            elif entity.dxftype == "INSERT":
                info = "{} {}".format(entity.name, entity.scale)
            elif entity.dxftype == "POLYLINE":
                info = "closed:{} np:{}".format (entity.is_closed, len(entity.points))
            elif entity.dxftype == "LWPOLYLINE":
                info = "closed:{} np:{}".format (entity.is_closed, len(entity.points))
            else:
                info = ''
            print ("  {} {}".format(entity, info))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Convert a DXF file to a KiCad footprint')
    parser.add_argument('DXF_file', help="DXF file")
    parser.add_argument('footprint_file', help="KiCad footprint file name", nargs='?')
    parser.add_argument('-v', '--verbose', help='Enable verbose output. -v shows brief information, -vv shows complete information', action='count')
    parser.add_argument('-d', '--dump', help='Dump the DXF file.', action='store_true')
    parser.add_argument('-u', '--units', help='File units: MM or MIL.', default="mm")
    args = parser.parse_args()

    if os.path.splitext(args.DXF_file)[1].lower() == ".dxf":

        if args.units.lower() == "mil":
            g_units = Units.MIL
            distance_error = to_mil (distance_error)
            min_line_width = to_mil (min_line_width)

        dxf = dxfgrabber.readfile(args.DXF_file)

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
