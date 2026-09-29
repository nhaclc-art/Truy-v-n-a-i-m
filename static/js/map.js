// Lớp bản đồ Leaflet: marker kết quả (màu theo danh mục, số theo thứ hạng), vị trí gốc,
// vòng bán kính, vòng sai số GPS, tuyến đường và vòng geofence.
/* global L */

const GEOFENCE_COLORS = { UNKNOWN: "#868e96", OUTSIDE: "#868e96", INSIDE: "#2f9e44" };

export const safeCategory = (id) => String(id).replace(/[^a-z0-9_]/g, "");

function textElement(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function popupContent(item) {
  const box = document.createElement("div");
  box.className = "popup";
  box.append(
    textElement("strong", item.name),
    textElement("div", `${item.category_label} · ${Math.round(item.distance_m)} m đường chim bay`, "popup-meta"),
  );
  return box;
}

function originIcon(mode) {
  return L.divIcon({ className: `origin-pin origin-${mode}`, iconSize: [22, 22], iconAnchor: [11, 11] });
}

export class ResultMap {
  constructor(element, { mapConfig, categories, origin, radius, onSelect, onOriginPick }) {
    this.onSelect = onSelect;
    this.onOriginPick = onOriginPick;
    this.picking = false;
    this.markers = new Map();
    this.mode = origin.mode;
    // Chiều cao phần bản đồ bị bảng trượt che ở màn hình hẹp (0 trên màn hình rộng).
    this.bottomInset = 0;

    const latlng = [origin.lat, origin.lon];
    // Đặt view trước khi thêm lớp để vòng tròn được chiếu tọa độ và getBounds() dùng được ngay.
    this.map = L.map(element, { zoomControl: false }).setView(latlng, 15);
    L.control.zoom({ position: "topright" }).addTo(this.map);
    this.addTiles(mapConfig);
    this.addLegend(categories);

    this.radiusCircle = L.circle(latlng, {
      radius,
      color: "#0b63ce",
      weight: 1.5,
      fillColor: "#0b63ce",
      fillOpacity: 0.05,
      interactive: false,
    }).addTo(this.map);
    this.accuracyCircle = L.circle(latlng, { radius: 1, color: "#0f766e", weight: 1, fillOpacity: 0.12, interactive: false });
    this.resultLayer = L.layerGroup().addTo(this.map);
    this.routeLayer = L.layerGroup().addTo(this.map);
    this.fenceLayer = L.layerGroup().addTo(this.map);
    this.whyNotLayer = L.layerGroup().addTo(this.map);
    this.itineraryLayer = L.layerGroup().addTo(this.map);

    this.originMarker = L.marker(latlng, {
      icon: originIcon(origin.mode),
      title: "Vị trí gốc",
      keyboard: false,
      zIndexOffset: 1000,
    }).addTo(this.map);
    this.originMarker.dragging.disable();
    this.originMarker.on("dragend", () => {
      const { lat, lng } = this.originMarker.getLatLng();
      this.onOriginPick(lat, lng);
    });
    this.map.on("click", (e) => {
      if (this.picking) this.onOriginPick(e.latlng.lat, e.latlng.lng);
    });

    this.fitToRadius();
  }

  addTiles(mapConfig) {
    const tiles = L.tileLayer(mapConfig.tile_url, {
      maxZoom: mapConfig.max_zoom,
      attribution: `&copy; <a href="${mapConfig.copyright_url}" target="_blank" rel="noopener">OpenStreetMap</a> contributors`,
    }).addTo(this.map);

    // Góc trên trái dành cho thẻ chỉ đường/geofence nổi trên bản đồ.
    const notice = L.control({ position: "bottomleft" });
    notice.onAdd = () => {
      this.tileNotice = textElement(
        "div",
        "Không tải được nền bản đồ (mất mạng hoặc máy chủ tile từ chối). Tìm kiếm vẫn hoạt động.",
        "map-notice",
      );
      this.tileNotice.hidden = true;
      return this.tileNotice;
    };
    notice.addTo(this.map);

    let failed = 0;
    tiles.on("loading", () => {
      failed = 0;
    });
    tiles.on("tileerror", () => {
      failed += 1;
    });
    tiles.on("load", () => {
      this.tileNotice.hidden = failed === 0;
    });
  }

  addLegend(categories) {
    const legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
      const box = document.createElement("div");
      box.className = "map-legend";
      for (const c of categories) {
        const row = document.createElement("div");
        row.append(textElement("span", "", `legend-dot cat-${safeCategory(c.id)}`), document.createTextNode(c.label));
        box.append(row);
      }
      L.DomEvent.disableClickPropagation(box);
      return box;
    };
    legend.addTo(this.map);
  }

  setOrigin({ lat, lon, mode, accuracy }) {
    const latlng = [lat, lon];
    this.originMarker.setLatLng(latlng);
    if (mode !== this.mode) {
      this.originMarker.setIcon(originIcon(mode));
      this.mode = mode;
    }
    this.radiusCircle.setLatLng(latlng);
    if (mode === "gps" && accuracy) {
      this.accuracyCircle.setLatLng(latlng).setRadius(accuracy).addTo(this.map);
    } else {
      this.accuracyCircle.remove();
    }
  }

  setRadius(radius) {
    this.radiusCircle.setRadius(radius);
  }

  setBottomInset(px) {
    this.bottomInset = px;
  }

  fitPadding(margin) {
    return { paddingTopLeft: [margin, margin], paddingBottomRight: [margin, margin + this.bottomInset] };
  }

  fitToRadius() {
    this.map.fitBounds(this.radiusCircle.getBounds(), this.fitPadding(24));
  }

  // Đưa một điểm vào giữa phần bản đồ còn nhìn thấy phía trên bảng trượt.
  panToVisible(latlng) {
    const zoom = this.map.getZoom();
    const point = this.map.project(latlng, zoom).add([0, this.bottomInset / 2]);
    this.map.panTo(this.map.unproject(point, zoom));
  }

  // Chế độ mô phỏng: bấm bản đồ hoặc kéo chấm gốc để đổi vị trí.
  setPicking(enabled) {
    this.picking = enabled;
    if (enabled) this.originMarker.dragging.enable();
    else this.originMarker.dragging.disable();
    this.map.getContainer().classList.toggle("picking", enabled);
  }

  showResults(items) {
    this.resultLayer.clearLayers();
    this.markers.clear();
    for (const item of items) {
      const icon = L.divIcon({
        className: `poi-pin cat-${safeCategory(item.category)}`,
        html: textElement("span", String(item.rank)),
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14],
      });
      const marker = L.marker([item.lat, item.lon], { icon, title: item.name, riseOnHover: true });
      marker.bindPopup(() => popupContent(item), { closeButton: false });
      marker.on("click", () => this.onSelect(item.id, "map"));
      marker.addTo(this.resultLayer);
      this.markers.set(item.id, marker);
    }
  }

  highlight(id, on) {
    const marker = this.markers.get(id);
    if (!marker) return;
    marker.getElement()?.classList.toggle("active", on);
    marker.setZIndexOffset(on ? 800 : 0);
  }

  focus(id) {
    const marker = this.markers.get(id);
    if (!marker) return;
    for (const other of this.markers.keys()) this.highlight(other, other === id);
    this.panToVisible(marker.getLatLng());
    // Popup tự dời bản đồ khi bị che; tính cả phần bảng trượt để popup không nằm dưới bảng.
    const popup = marker.getPopup();
    if (popup) popup.options.autoPanPaddingBottomRight = L.point(5, this.bottomInset + 5);
    marker.openPopup();
  }

  showRoute(path) {
    this.routeLayer.clearLayers();
    const casing = L.polyline(path, { color: "#ffffff", weight: 9, opacity: 0.9, interactive: false });
    const line = L.polyline(path, { color: "#0b63ce", weight: 5, opacity: 0.95, interactive: false });
    this.routeLayer.addLayer(casing).addLayer(line);
    this.map.fitBounds(line.getBounds(), this.fitPadding(48));
  }

  clearRoute() {
    this.routeLayer.clearLayers();
  }

  showGeofence(target, enterM, exitM) {
    this.fenceLayer.clearLayers();
    const latlng = [target.lat, target.lon];
    this.fenceExit = L.circle(latlng, { radius: exitM, color: "#868e96", weight: 1.5, dashArray: "6 6", fill: false, interactive: false });
    this.fenceEnter = L.circle(latlng, { radius: enterM, color: "#868e96", weight: 2, fillOpacity: 0.12, interactive: false });
    this.fenceLayer.addLayer(this.fenceExit).addLayer(this.fenceEnter);
  }

  setGeofenceState(state) {
    const color = GEOFENCE_COLORS[state] ?? GEOFENCE_COLORS.UNKNOWN;
    this.fenceEnter?.setStyle({ color, fillColor: color });
  }

  clearGeofence() {
    this.fenceLayer.clearLayers();
    this.fenceEnter = this.fenceExit = null;
  }

  // Lộ trình nhiều chặng: điểm gốc + các chặng đánh số, nối bằng đường nét đứt (ước tính, chưa phải
  // tuyến đi bộ thật). showItineraryLegPath() vẽ chồng lên bằng tuyến thật khi có, theo từng chặng.
  showItineraryStops(originLatLng, stops) {
    this.itineraryLayer.clearLayers();
    const straight = L.polyline([originLatLng, ...stops.map((s) => [s.lat, s.lon])], {
      color: "#c2255c",
      weight: 3,
      opacity: 0.7,
      dashArray: "2 8",
      interactive: false,
    });
    this.itineraryLayer.addLayer(straight);
    stops.forEach((s, i) => {
      const icon = L.divIcon({ className: "itinerary-pin", html: textElement("span", String(i + 1)), iconSize: [26, 26], iconAnchor: [13, 13] });
      const marker = L.marker([s.lat, s.lon], { icon, title: s.name, keyboard: false, zIndexOffset: 950 });
      marker.bindTooltip(textElement("span", `${i + 1}. ${s.name}`), { direction: "top", offset: [0, -12] });
      this.itineraryLayer.addLayer(marker);
    });
    this.map.fitBounds(straight.getBounds(), this.fitPadding(48));
  }

  // Tuyến đi bộ thật (OSRM) của một chặng, gọi thêm mỗi khi một chặng tính xong; vẽ chồng lên đường ước tính.
  showItineraryLegPath(path) {
    const casing = L.polyline(path, { color: "#ffffff", weight: 7, opacity: 0.9, interactive: false });
    const line = L.polyline(path, { color: "#c2255c", weight: 4, opacity: 0.95, interactive: false });
    this.itineraryLayer.addLayer(casing).addLayer(line);
  }

  clearItinerary() {
    this.itineraryLayer.clearLayers();
  }

  // Địa điểm người dùng hỏi "Vì sao không có?": hiện cả khi không nằm trong kết quả.
  showWhyNotTarget(target) {
    this.whyNotLayer.clearLayers();
    const icon = L.divIcon({ className: "whynot-pin", html: textElement("span", "?"), iconSize: [30, 30], iconAnchor: [15, 15] });
    const marker = L.marker([target.lat, target.lon], { icon, title: target.name, keyboard: false, zIndexOffset: 900 });
    marker.bindTooltip(textElement("span", `Đang hỏi: ${target.name}`), { direction: "top", offset: [0, -14] });
    marker.addTo(this.whyNotLayer);
    this.panToVisible(marker.getLatLng());
  }

  clearWhyNotTarget() {
    this.whyNotLayer.clearLayers();
  }
}
