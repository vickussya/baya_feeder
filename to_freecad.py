import FreeCAD, Part, glob, os
root = r"c:\Users\vikto\OneDrive\Documenten\git\Baya feeder\baya_feeder"
doc = FreeCAD.openDocument(os.path.join(root, "baya feeder.FCStd"))
asm = doc.getObject("Assembly")
for p in sorted(glob.glob(os.path.join(root, "step", "[0-9]*.step"))):
    label = os.path.splitext(os.path.basename(p))[0]
    shp = Part.Shape(); shp.read(p)
    obj = doc.addObject("Part::Feature", "P" + label)
    obj.Label = label
    obj.Shape = shp
    asm.addObject(obj)
    print("added", label, round(shp.Volume / 1000, 1), "ml", shp.isValid())
doc.recompute()
doc.save()
print("saved", doc.FileName, "objects:", len(doc.Objects))
