import json, math, sys, cv2, numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPixmap, QPen, QBrush, QPolygonF
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QToolBar, QFileDialog, QMessageBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPolygonItem,
    QGraphicsTextItem, QGraphicsItem, QInputDialog, QHBoxLayout, QWidget
)
import rasterio
from rasterio.transform import xy, rowcol
from shapely.geometry import Polygon, mapping
import fiona
from openpyxl import Workbook
from pyproj import Geod, Transformer

# ───── 基础工具 ─────────────────────────────────────────────
GEOD = Geod(ellps="WGS84")

def planar_area_perimeter(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
    if len(pts) < 3: return 0.0, 0.0
    area = peri = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
        peri += math.hypot(x2 - x1, y2 - y1)
    return abs(area) * 0.5, peri

def geod_area_perimeter(lon, lat):
    if len(lon) < 3: return 0.0, 0.0
    if lon[0] != lon[-1] or lat[0] != lat[-1]:
        lon = lon + lon[:1]; lat = lat + lat[:1]
    a, p = GEOD.polygon_area_perimeter(lon, lat)
    return abs(a), p

def looks_like_lonlat(xs, ys):
    return all(-180 <= x <= 180 for x in xs) and all(-90 <= y <= 90 for y in ys)

def pixel_to_map(tf, col, row): return xy(tf, row, col) if tf else (col, row)
def map_to_pixel(tf, x, y):     return rowcol(tf, x, y)[::-1] if tf else (x, y)

# ───── 标注元素 ─────────────────────────────────────────────
class RectAnn(QGraphicsRectItem):
    def __init__(self, r_px: QRectF, label: str, tf):
        super().__init__(r_px)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setPen(QPen(Qt.red, 2)); self.setBrush(QBrush(Qt.transparent))
        self.txt = QGraphicsTextItem(label, self); self.txt.setDefaultTextColor(Qt.yellow)
        self.txt.setPos(r_px.topLeft())
        tl = pixel_to_map(tf, r_px.left(),  r_px.top())
        br = pixel_to_map(tf, r_px.right(), r_px.bottom())
        self.map_rect = {"tl":{"x":tl[0],"y":tl[1]}, "br":{"x":br[0],"y":br[1]}}
    def label(self): return self.txt.toPlainText()
    def to_dict(self):
        return {"type":"rect",
                "x":self.map_rect["tl"]["x"], "y":self.map_rect["tl"]["y"],
                "w":self.map_rect["br"]["x"]-self.map_rect["tl"]["x"],
                "h":self.map_rect["br"]["y"]-self.map_rect["tl"]["y"],
                "label":self.label()}

class PolyAnn(QGraphicsPolygonItem):
    def __init__(self, poly_px: QPolygonF, label: str, tf):
        super().__init__(poly_px)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setPen(QPen(Qt.blue, 2)); self.setBrush(QBrush(Qt.transparent))
        self.txt = QGraphicsTextItem(label, self); self.txt.setDefaultTextColor(Qt.yellow)
        self.txt.setPos(self.polygon().boundingRect().topLeft())
        self.map_pts=[{"x":pixel_to_map(tf,p.x(),p.y())[0],
                       "y":pixel_to_map(tf,p.x(),p.y())[1]} for p in poly_px]
    def label(self): return self.txt.toPlainText()
    def to_dict(self): return {"type":"poly","points":self.map_pts,"label":self.label()}

# ───── 画布 ────────────────────────────────────────────────
class Canvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scn=QGraphicsScene(self); self.setScene(self.scn)
        self.img_item=None; self.transform=None; self.crs=None
        self.mode=None; self.drawing=False; self.origin=QPointF()
        self.temp_rect=None; self.poly_pts=[]; self.temp_poly=None
    def set_mode(self,m):
        self.mode=m; self.drawing=False; self.poly_pts.clear()
        if self.temp_rect:self.scn.removeItem(self.temp_rect); self.temp_rect=None
        if self.temp_poly:self.scn.removeItem(self.temp_poly); self.temp_poly=None
    def load_img(self,p:Path):
        pm=QPixmap(str(p)); self.scn.clear(); self.img_item=self.scn.addPixmap(pm)
        self.fitInView(self.img_item, Qt.KeepAspectRatio)
        try: ds=rasterio.open(p); self.transform,self.crs=ds.transform,ds.crs
        except: self.transform=self.crs=None
    def anns(self): return [i for i in self.scn.items() if isinstance(i,(RectAnn,PolyAnn))]
    def clear_anns(self): [self.scn.removeItem(a) for a in self.anns()]
    # ----- 绘制多边形 (简版) -----
    def mousePressEvent(self,e):
        if not self.img_item: return super().mousePressEvent(e)
        if self.mode=="poly":
            pt=self.mapToScene(e.pos())
            if e.button()==Qt.LeftButton:
                self.poly_pts.append(pt)
                if not self.temp_poly:
                    self.temp_poly=self.scn.addPolygon(QPolygonF(self.poly_pts),QPen(Qt.green,1,Qt.DashLine))
                else:self.temp_poly.setPolygon(QPolygonF(self.poly_pts)); return
            elif e.button()==Qt.RightButton and len(self.poly_pts)>=3:
                label,ok=QInputDialog.getText(self,"标签","输入标签：")
                if ok and label:self.scn.addItem(PolyAnn(QPolygonF(self.poly_pts),label,self.transform))
                if self.temp_poly:self.scn.removeItem(self.temp_poly)
                self.temp_poly=None; self.poly_pts.clear(); return
        super().mousePressEvent(e)

# ───── 主窗口 ─────────────────────────────────────────────
class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Image Annotator v5.5"); self.resize(1200,800)
        self.canvas=Canvas(); cw=QWidget(); QHBoxLayout(cw).addWidget(self.canvas); self.setCentralWidget(cw)
        self.current:Optional[Path]=None; self._ui()
    # ---------- 灰度读取 (兼容 GeoTIFF) ----------
    def _load_gray(self,path:Path):
        img=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if img is not None: return img
        # tif fallback
        with rasterio.open(path) as ds:
            arr=ds.read(1).astype(np.float32)
            arr-=arr.min(); rng=arr.max()
            if rng: arr/=rng
            return (arr*255).astype(np.uint8)
    # ---------- UI ----------
    def _ui(self):
        tb=QToolBar("工具",self); self.addToolBar(tb)
        tb.addAction("打开图片",self.open_img)
        tb.addAction("保存标注",self.save_json)
        tb.addAction("载入标注",self.load_json)
        tb.addAction("清空标注",self.canvas.clear_anns); tb.addSeparator()
        self.act_poly=QAction("多边形",self,checkable=True,triggered=lambda:self.canvas.set_mode("poly"))
        tb.addAction(self.act_poly); tb.addSeparator()
        tb.addAction("注意力校正",self.attention_refine)
        tb.addAction("导出外接矩形",self.export_bbox_json)
        tb.addAction("批量面积周长",self.batch_stats_json)
        tb.addAction("批量转SHP",self.batch_json_to_shp)
    # ---------- I/O ----------
    def open_img(self):
        fn,_=QFileDialog.getOpenFileName(self,"","","*.tif *.tiff *.png *.jpg *.jpeg *.bmp")
        if fn: self.canvas.load_img(Path(fn)); self.current=Path(fn)
    def save_json(self):
        anns=self.canvas.anns()
        if not anns: return QMessageBox.information(self,"提示","没有标注")
        out=self.current.with_suffix(".json")
        out.write_text(json.dumps([a.to_dict() for a in anns],ensure_ascii=False,indent=2),"utf-8")
        QMessageBox.information(self,"保存",f"已写入\n{out}")
    def load_json(self):
        fn,_=QFileDialog.getOpenFileName(self,"载入标注","","JSON (*.json)")
        if not fn:return
        data=json.loads(Path(fn).read_text("utf-8")); tf=self.canvas.transform; self.canvas.clear_anns()
        for ann in data:
            if ann["type"]=="poly":
                pts=[QPointF(*map_to_pixel(tf,p["x"],p["y"])) for p in ann["points"]]
                self.canvas.scn.addItem(PolyAnn(QPolygonF(pts),ann.get("label",""),tf))
    # ---------- 注意力校正 ----------
    def attention_refine(self):
        if not (self.current and self.canvas.anns()): return
        img=self._load_gray(self.current)
        h,w=img.shape
        for ann in self.canvas.anns():
            pts=[(p.x(),p.y()) for p in ann.polygon()]
            xs,ys=zip(*pts); minx,maxx=int(min(xs))-5,int(max(xs))+5
            miny,maxy=int(min(ys))-5,int(max(ys))+5
            minx=max(0,minx); miny=max(0,miny)
            maxx=min(w,maxx); maxy=min(h,maxy)
            roi=img[miny:maxy,minx:maxx]
            if roi.size==0: continue
            sob=cv2.Sobel(cv2.GaussianBlur(roi,(3,3),0),cv2.CV_64F,1,1,ksize=3)
            mag=cv2.convertScaleAbs(sob)
            new=[]
            for x,y in pts:
                sub=mag[int(y)-miny:int(y)-miny+3,int(x)-minx:int(x)-minx+3]
                if sub.size:
                    dy,dx=np.unravel_index(sub.argmax(),sub.shape); new.append((x+dx-1,y+dy-1))
                else:new.append((x,y))
            ann.setPolygon(QPolygonF([QPointF(px,py) for px,py in new]))
            ann.map_pts=[{"x":pixel_to_map(self.canvas.transform,px,py)[0],
                          "y":pixel_to_map(self.canvas.transform,px,py)[1]} for px,py in new]
        QMessageBox.information(self,"完成","已校正顶点")
    # ---------- 其余导出/批量函数与前版本一致 ----------
    def export_bbox_json(self):
        polys=[a for a in self.canvas.anns() if isinstance(a,PolyAnn)]
        if not polys:return
        out=[]
        for p in polys:
            br=p.polygon().boundingRect()
            tl=pixel_to_map(self.canvas.transform,br.left(),br.top())
            brm=pixel_to_map(self.canvas.transform,br.right(),br.bottom())
            out.append({"type":"rect","x":tl[0],"y":tl[1],"w":brm[0]-tl[0],"h":brm[1]-tl[1],"label":p.label()})
        self.current.with_suffix("_bbox.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
        QMessageBox.information(self,"导出","_bbox.json 已保存")
    def batch_stats_json(self):
        folder=QFileDialog.getExistingDirectory(self,"选择包含 JSON 的文件夹"); 0
        if not folder:return
        wb=Workbook(); ws=wb.active; ws.title="stats"; ws.append(["文件名","label","面积(m²)","周长(m)"]); cnt=0
        for fp in Path(folder).glob("*.json"):
            try:data=json.loads(fp.read_text("utf-8"))
            except:continue
            for ann in data:
                if ann["type"]!="poly":continue
                xs,ys=zip(*[(p["x"],p["y"]) for p in ann["points"]])
                area,peri=geod_area_perimeter(list(xs),list(ys)) if looks_like_lonlat(xs,ys) else planar_area_perimeter(list(zip(xs,ys)))
                ws.append([fp.name,ann.get("label",""),f"{area:.4f}",f"{peri:.4f}"]); cnt+=1
        if not cnt:return QMessageBox.information(self,"提示","未找到多边形")
        out=Path(folder)/"stats_area_perimeter.xlsx"; wb.save(out)
        QMessageBox.information(self,"完成",f"结果已保存到\n{out}")
    def batch_json_to_shp(self):
        folder=QFileDialog.getExistingDirectory(self,"选择包含 JSON 的文件夹"); 0
        if not folder:return
        for fp in Path(folder).glob("*.json"):
            try:data=json.loads(fp.read_text("utf-8"))
            except:continue
            shp=fp.with_suffix(".shp"); schema={"geometry":"Polygon","properties":{"label":"str"}}
            with fiona.open(shp,"w",driver="ESRI Shapefile",crs="EPSG:4326",schema=schema) as dst:
                for ann in data:
                    if ann["type"]!="poly":continue
                    xs,ys=zip(*[(p["x"],p["y"]) for p in ann["points"]])
                    if not looks_like_lonlat(xs,ys):
                        if self.canvas.crs:
                            xs,ys=Transformer.from_crs(self.canvas.crs,4326,always_xy=True).transform(xs,ys)
                    dst.write({"geometry":mapping(Polygon(zip(xs,ys))),"properties":{"label":ann.get("label","")}})
        QMessageBox.information(self,"完成","已批量生成 SHP")

# ───── main ───────────────────────────────────────────────
if __name__=="__main__":
    app=QApplication(sys.argv); Main().show(); sys.exit(app.exec_())
