// Chạy: node --test tests/js/geofence.test.mjs  (Node 22+)
import assert from "node:assert/strict";
import { test } from "node:test";

import { Geofence, haversineM, INSIDE, OUTSIDE, UNKNOWN } from "../../static/js/geofence.js";

const CONFIG = { enter_m: 100, exit_m: 130, confirm_samples: 2, cooldown_s: 30, max_accuracy_m: 50 };
const TARGET = { id: "poi-1", name: "Điểm thử", lat: 10.761357, lon: 106.6821769 };
const METERS_PER_DEGREE_LAT = (6371008.8 * Math.PI) / 180;

// Mẫu cách TARGET đúng `meters` về phía bắc (cùng kinh độ nên khoảng cách Haversine = meters).
const at = (meters, t, extra = {}) => ({
  lat: TARGET.lat + meters / METERS_PER_DEGREE_LAT,
  lon: TARGET.lon,
  accuracy: null,
  timestamp: t,
  mode: "simulated",
  ...extra,
});

const feed = (fence, samples) => samples.map((s) => fence.update(s));
const events = (results) => results.filter((r) => r.event).map((r) => r.event.type);

test("haversine matches the backend formula", () => {
  assert.equal(haversineM(10, 106, 10, 106), 0);
  assert.ok(Math.abs(haversineM(0, 0, 1, 0) - 111195.08) < 0.1);
});

test("first sample initializes state without an event", () => {
  const fence = new Geofence(TARGET, CONFIG);
  assert.equal(fence.state, UNKNOWN);

  const r = fence.update(at(50, 0));
  assert.equal(r.state, INSIDE);
  assert.equal(r.initialized, true);
  assert.equal(r.event, null);
});

test("entering needs two consecutive inside samples", () => {
  const fence = new Geofence(TARGET, CONFIG);
  fence.update(at(300, 0));

  const first = fence.update(at(80, 1000));
  assert.equal(first.event, null);
  assert.deepEqual(first.pending, { to: INSIDE, count: 1, needed: 2 });

  const second = fence.update(at(80, 2000));
  assert.equal(second.state, INSIDE);
  assert.equal(second.event.type, "enter");
  assert.equal(second.event.mode, "simulated");
  assert.equal(second.event.notified, true);
});

test("an outside sample breaks the confirmation streak", () => {
  const fence = new Geofence(TARGET, CONFIG);
  const results = feed(fence, [at(300, 0), at(80, 1000), at(300, 2000), at(80, 3000)]);

  assert.deepEqual(events(results), []);
  assert.equal(fence.state, OUTSIDE);
});

test("the 100-130 m band keeps the previous state (no spam at the boundary)", () => {
  const fence = new Geofence(TARGET, CONFIG);
  feed(fence, [at(300, 0), at(50, 1000), at(50, 2000)]);
  assert.equal(fence.state, INSIDE);

  const wobble = [95, 105, 99, 120, 101, 129, 98, 110].map((m, i) => at(m, 3000 + i * 1000));
  assert.deepEqual(events(feed(fence, wobble)), []);
  assert.equal(fence.state, INSIDE);
});

test("exit needs two samples at or beyond 130 m", () => {
  const fence = new Geofence(TARGET, CONFIG);
  feed(fence, [at(300, 0), at(50, 1000), at(50, 2000)]);

  const results = feed(fence, [at(131, 40000), at(125, 41000), at(131, 42000), at(140, 43000)]);
  assert.deepEqual(events(results), ["exit"]);
  assert.equal(fence.state, OUTSIDE);
});

test("cooldown suppresses notifications but still records the transition", () => {
  const fence = new Geofence(TARGET, CONFIG);
  feed(fence, [at(300, 0), at(50, 1000), at(50, 2000)]); // enter, thông báo lúc 2000

  const exit = feed(fence, [at(200, 9000), at(200, 10000)]).at(-1).event;
  assert.equal(exit.type, "exit");
  assert.equal(exit.notified, false);

  const enter = feed(fence, [at(50, 44000), at(50, 45000)]).at(-1).event;
  assert.equal(enter.type, "enter");
  assert.equal(enter.notified, true);
});

test("low-accuracy real samples hold state and break the streak", () => {
  const fence = new Geofence(TARGET, CONFIG);
  fence.update(at(300, 0, { mode: "gps", accuracy: 10 }));

  const noisy = fence.update(at(80, 1000, { mode: "gps", accuracy: 80 }));
  assert.equal(noisy.lowAccuracy, true);
  assert.equal(noisy.state, OUTSIDE);

  const results = feed(fence, [
    at(80, 2000, { mode: "gps", accuracy: 10 }),
    at(80, 3000, { mode: "gps", accuracy: 90 }),
    at(80, 4000, { mode: "gps", accuracy: 10 }),
  ]);
  assert.deepEqual(events(results), []);

  const confirmed = fence.update(at(80, 5000, { mode: "gps", accuracy: 10 }));
  assert.equal(confirmed.event.type, "enter");
  assert.equal(confirmed.event.mode, "gps");
});

test("reset returns to UNKNOWN and the next sample does not create a fake event", () => {
  const fence = new Geofence(TARGET, CONFIG);
  feed(fence, [at(300, 0), at(50, 1000), at(50, 2000)]);
  fence.reset();
  assert.equal(fence.state, UNKNOWN);

  const r = fence.update(at(50, 3000));
  assert.equal(r.initialized, true);
  assert.equal(r.event, null);
});
