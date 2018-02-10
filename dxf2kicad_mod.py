# refer to http://pythonhosted.org/dxfgrabber/
#
# Note that there must not be any line or shape overlapped

# Add support for LWPOLYLINE
# Bob Cousins 2018-02

import dxfgrabber
from math import *
import math
import sys

global debug
global distance_error
global body_head
global body_end
global fp_poly_head
global fp_poly_end
global cur_poly

debug = False
distance_error = 1e-2

body_head = "\n\
(module dxf2kicad (layer F.Cu) (tedit 0) \n\
  (fp_text reference REF*** (at 0 -4) (layer F.SilkS) hide \n\
    (effects (font (thickness 0.2))) \n\
  ) \n\
  (fp_text value VAL (at 0 4) (layer F.SilkS) hide \n\
    (effects (font (thickness 0.2))) \n\
  ) "

body_end = "\n)"

fp_poly_head =   "(fp_poly \
  (pts "
fp_poly_end_1 = " ) \n\
  (layer "

fp_poly_end_2 = " ) (width 0.001)) "

def dbg (s):
    if debug:
        print >>sys.stderr, s

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
    if debug:
      print  >>sys.stderr,"LINE ", entity.start, entity.end
    return (entity.start,entity.end)
  elif "ARC" == entity.dxftype:

    start = ( entity.center[0] + entity.radius * math.cos(radians(entity.start_angle)),
              entity.center[1] + entity.radius * math.sin(radians(entity.start_angle)), 0)
    end = ( entity.center[0] + entity.radius * math.cos(radians(entity.end_angle)),
            entity.center[1] + entity.radius * math.sin(radians(entity.end_angle)), 0)
    if debug:
      print  >>sys.stderr,"ARC ", start, end
    return (start,end)

  elif entity.dxftype == "LWPOLYLINE":
    return (entity.points[0], entity.points[-1])

  else:
    print >>sys.stderr, "[Error]: Unexpected dxftype ",  entity.dxftype


def is_poly (entity):
    if entity.dxftype in ['LWPOLYLINE']:
        return True
    else:
        return False
#
def print_points(ety, direction):

  points = []
  if 'LINE' == ety.dxftype:
    points = [ety.start, ety.end]
  elif 'ARC' == ety.dxftype:

    step = 1.0/ety.radius
    angle = ety.start_angle

    if debug:
      print >>sys.stderr,"angle", ety.start_angle, ety.end_angle

    if (ety.start_angle > ety.end_angle):
      ety.end_angle += 360
    while True:
      points.append( (ety.center[0] + ety.radius * math.cos(radians(angle)),
                      ety.center[1] + ety.radius * math.sin(radians(angle))) )
      angle +=  step

      if (angle > ety.end_angle):
        break
  elif ety.dxftype == "LWPOLYLINE":
    for j,point in enumerate(ety.points):

        if j == len(ety.points)-1:
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
    print "[Error]: Unexpected dxftype ",  entity.dxftype

  #
  if direction == -1:
    points.reverse()

  for point in points[0:-1]:
    cur_poly.append (point)


#
def start_new_shape():
  global current_shape, points, point_to_close, pts_next, cur_poly

  if cur_poly:

      # clip to poly
      clip_poly = []
      clip_poly.append ([-20,6])
      clip_poly.append ([20,6])
      clip_poly.append ([20,5])
      clip_poly.append ([-20,5])
      #cur_poly = clip (cur_poly, clip_poly)

      print fp_poly_head
      for point in cur_poly:
        print "(xy ", point[0]," ", -point[1],")" #in KiCad Y axis has opposite direction
      print fp_poly_end_1, layer, fp_poly_end_2
      #print fp_poly_end_1, "F.SilkS", fp_poly_end_2

  cur_poly = []

  if len(not_processed_data) > 0:
    current_shape = not_processed_data.pop() #pick up one
    points = get_start_end_pts(current_shape)

    point_to_close = points[0]
    pts_next = points[1]

    if debug:
      print >>sys.stderr,"starting point",point_to_close

    print_points(current_shape, 1)
  else:
    pts_next = None
#
#
#

#dxf = dxfgrabber.readfile("test4-R2000-2002.dxf")
dxf = dxfgrabber.readfile(sys.argv[1])

if len(sys.argv)>2 and sys.argv[2] == "-d":
  debug = True

if debug:
  print >>sys.stderr,"DXF version: ", dxf.dxfversion

header_var_count = len(dxf.header) # dict of dxf header vars
layer_count = len(dxf.layers) # collection of layer definitions
block_definition_count = len(dxf.blocks) #  dict like collection of block definitions
entity_count = len(dxf.entities) # list like collection of entities

if debug:
  print >>sys.stderr,"Entity Count: ", entity_count

layers = set([entity.layer for entity in dxf.entities])
if debug:
  print >>sys.stderr, "Layers:", layers

print body_head
cur_poly = []

for layer in layers:

  not_processed_data = set([entity for entity in dxf.entities if entity.layer == layer])

  pts = None

  start_new_shape()

  if debug :
    print >>sys.stderr,"Not Processed Shape: ", len(not_processed_data)

  while True:

    if pts_next == None:
      if debug:
        print >>sys.stderr, "pts_next is None"
      break #stop

    if is_poly (current_shape):
        if debug:
            print >>sys.stderr, "cur is poly"

        start_new_shape()
        continue

    #
    pts = pts_next

    if debug:
      print >>sys.stderr,"Searching entity which is connected with ", pts

    #get_start_end_pts(current_shape)
    matched_entity = None

    for entity in not_processed_data:
      points = get_start_end_pts(entity)
      x = points[0][0]
      y = points[0][1]
      if (math.fabs(x-pts[0]) < 5e-2) and (math.fabs(y-pts[1]) < 5e-2):
        #matched
        matched_entity = entity
        direction = 1 #from start to end
        pts_next = points[1]
        if debug:
          print >>sys.stderr,"Got the Point", x, y
        break
      x = points[1][0]
      y = points[1][1]
      if (math.fabs(x-pts[0]) < distance_error) and (math.fabs(y-pts[1]) < distance_error):
        #matched
        matched_entity = entity
        direction = -1 #from end to start
        pts_next = points[0]
        if debug:
          print >>sys.stderr,"Got the Point", x, y
        break


    if matched_entity == None:

      if debug:
        print >>sys.stderr,"No matching found, check if we could close the loop"

      if ( (math.fabs(point_to_close[0]-pts[0]) < distance_error) and 
           (math.fabs(point_to_close[1]-pts[1]) < distance_error) ):
        if debug:
          print >>sys.stderr,"shape closed at", pts

        cur_poly.append (pts)

        #find next shape
        start_new_shape()

        if debug :
          print >>sys.stderr,"Not Processed Shape: ", len(not_processed_data)
      else:
        print >>sys.stderr, "[Error] unconnected Point:",pts ," on layer", layer
        print >>sys.stderr, "        there may be overlapped lines or arcs or unclosed shape, please double check the dxf file"

        break;
    else:
      if debug:
        print >>sys.stderr, "now print the line on,", matched_entity

      print_points(matched_entity, direction)

      if debug:
        print >>sys.stderr, "removed from the set,", matched_entity
      not_processed_data.remove(matched_entity) #remove from the set

      if debug :
        print  >>sys.stderr,"Not Processed Shape: ", len(not_processed_data)

print body_end