# coding=utf-8
import os

import xml.etree.cElementTree as ET
import json

class Event(object):
    def __init__(self, target, start, level):
        self.target = target
        self.start = start
        self.level = level
        self._end = None
        self.children = []

    def _get_end(self):
        if self._end is None:
            if self.children:
                self._end = self.children[-1].end
            else:
                self._end = self.start + 1
        return self._end

    def _set_end(self, value):
        self._end = value

    end = property(_get_end, _set_end)

    def _get_length(self):
        return self.end - self.start

    length = property(_get_length)


class Data(object):
    def __init__(self, blob):
        self.blob = blob
        self.root = None
        self.parse()

    @classmethod
    def from_file(cls, fp):
        if isinstance(fp, basestring):
            fp = open(fp, "rb")
        return cls(json.load(fp))

    def parse(self):
        time_scale = float(self.blob["tscale"])
        stack = []
        for evt in self.blob["e"]:
            if not evt:
                continue
            event_type, time, level, target = evt
            time /= time_scale
            target = target.split("^")
            if event_type == "call":
                ent = Event(target, time, level)
                if not self.root:
                    stack.append(ent)
                    self.root = ent
                else:
                    if stack:
                        stack[-1].children.append(ent)
                        stack.append(ent)
                    else:
                        print "+++", evt
            elif event_type == "return" or event_type == "c_exception":
                if not stack:
                    print "???", evt
                else:
                    #print target, stack[-1].target
                    if event_type != "c_exception":
                        assert target[-1] == stack[-1].target[-1], (target, stack[-1].target)
                    stack[-1].end = time
                    stack.pop()
            else:
                print "Ignoring event of type", event_type
                #raise ValueError("nope")

    def dump(self):
        def walk(event, level):
            print "%s%s (%.2fms)" % ("  " * level, event.target, event.length)
            for child in event.children:
                walk(child, level+1)


        walk(self.root, 0)

    def render_svg(self, pixels_per_msec):
        svg = SVG()

        def time_to_x(time):
            return time * pixels_per_msec

        def level_to_y(level):
            return level * 20

        maxes = [0, 0, 0]

        def walk(event, level=0):
            #if (event.end - event.start) < 0.00001:
            #	return
            x0 = time_to_x(event.start)
            x1 = time_to_x(event.end)
            if (x1 - x0) < 2:
                return

            y0 = level_to_y(level)
            y1 = level_to_y(level + 1)
            title = event.target[-1]
            svg.rect(
                x=x0, y=y0, width=x1-x0, height=y1-y0,
                style=Style(stroke_width=1, fill="white", stroke="#003300"),
                title=title,
            )
            svg.text(x=x0 + 2, y=y1 - 3, text=title, style=Style(font="9px sans-serif"))
            for child in event.children:
                walk(child, level+1)

            maxes[0] = max(x1, maxes[0])
            maxes[1] = max(y1, maxes[1])
            maxes[2] = max(event.end, maxes[2])

        walk(self.root)

        time = 0
        while time < maxes[2]:
            x = time_to_x(time)
            svg.text(x=x, y=15, text="%.2fms" % time, style=Style(font="11px sans-serif"))
            svg.line(x1=x, y1=0, x2=x, y2=maxes[1], style=Style(stroke_width=1, stroke="#CCFFCC"))
            time += 100


        svg.root.attrib["width"] = str(maxes[0])
        svg.root.attrib["height"] = str(maxes[1])
        return svg

def El(name, **kwargs):
    _text = kwargs.pop("_text", None)
    element = ET.Element(name, **dict((k, unicode(v)) for (k, v) in kwargs.iteritems() if v not in ("", None)))
    if _text:
        element.text = unicode(_text)
    return element

def Style(**kwargs):
    return ";".join("%s:%s" % (unicode(k).replace("_", "-"), v) for (k, v) in kwargs.iteritems() if v not in ("", None))

class SVG(object):

    def __init__(self):
        self.root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg")
        self.stack = [self.root]

    def write(self, fp):
        ET.ElementTree(self.root).write(fp, encoding="UTF-8")

    def rect(self, x, y, width, height, **kwargs):
        title = kwargs.pop("title", None)
        el = El("rect", x=x, y=y, width=width, height=height, **kwargs)
        if title:
            el.append(El("title", _text=title))
        self.stack[-1].append(el)

    def text(self, x, y, text, **kwargs):
        el = El("text", x=x, y=y, _text=text, **kwargs)
        self.stack[-1].append(el)

    def line(self, x1, y1, x2, y2, **kwargs):
        el = El("line", x1=x1, y1=y1, x2=x2, y2=y2, **kwargs)
        self.stack[-1].append(el)

def cmdline():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=argparse.FileType())
    ap.add_argument("-o", "--output", default=None, type=argparse.FileType())
    ap.add_argument("-x", "--x-scale", type=float, default=300, help="pixels per msec")
    args = ap.parse_args()
    jd = Data.from_file(args.input)
    if not args.output:
        input_filename = getattr(args.input, "name", "defiler.json")
        args.output = os.path.splitext(input_filename)[0] + ".svg"
    s = jd.render_svg(pixels_per_msec=args.x_scale)
    s.write(args.output)
    print "Wrote: %s" % args.output



if __name__ == "__main__":
    cmdline()