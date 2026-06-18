#!/usr/bin/env python3
# =====================================================================
#  mqtt_publisher.py  -  Phase 4: MQTT Cloud Publisher
# ---------------------------------------------------------------------
#  ดึงค่าจาก Flask API -> รวมเป็น JSON ก้อนเดียว -> ส่งไป MQTT topic
#  ทุกอย่างกำหนดใน mqtt_config.yml  แก้ yml + save = reload ทันที
# =====================================================================

import os
import time
import json
import logging
import threading
from urllib.request import urlopen
from urllib.error import URLError

import yaml
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mqtt_publisher")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mqtt_config.yml")


# =====================================================================
#  Config Manager — live-reload ด้วย mtime check
# =====================================================================
class ConfigManager:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._mtime = None
        self._config = None
        self.reload(force=True)

    def reload(self, force=False):
        try:
            mtime = os.path.getmtime(self.path)
        except OSError as e:
            log.error("ไม่พบไฟล์ config: %s", e)
            return False

        if not force and mtime == self._mtime:
            return False

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                new_cfg = yaml.safe_load(f)
        except Exception as e:
            log.error("parse mqtt_config.yml ผิดพลาด (ใช้ค่าเดิม): %s", e)
            return False

        with self._lock:
            self._config = new_cfg
            self._mtime = mtime

        if not force:
            log.info("mqtt_config.yml เปลี่ยนแปลง -> โหลด config ใหม่แล้ว")
        return True

    @property
    def config(self):
        with self._lock:
            return self._config


# =====================================================================
#  MQTT Manager — reconnect อัตโนมัติเมื่อ broker/credential เปลี่ยน
# =====================================================================
class MqttManager:
    def __init__(self):
        self.client = None
        self._sig = None
        self._lock = threading.Lock()

    def _make_sig(self, mc):
        return (
            mc.get("broker"), mc.get("port"),
            mc.get("username"), mc.get("password"),
            mc.get("use_tls", False), mc.get("client_id", "jk_bms_pi4"),
        )

    def ensure_connected(self, mc):
        sig = self._make_sig(mc)
        with self._lock:
            if self.client is not None and sig == self._sig:
                return self.client

            if self.client is not None:
                try:
                    self.client.loop_stop()
                    self.client.disconnect()
                except Exception:
                    pass
                log.info("MQTT broker config เปลี่ยน -> reconnect ใหม่")

            client = mqtt.Client(
                client_id=mc.get("client_id", "jk_bms_pi4"),
                protocol=mqtt.MQTTv311,
            )

            if mc.get("username"):
                client.username_pw_set(mc.get("username"), mc.get("password"))

            if mc.get("use_tls", False):
                client.tls_set()

            client.on_connect = lambda c, u, f, rc: (
                log.info("MQTT connected (%s:%s)", mc.get("broker"), mc.get("port"))
                if rc == 0 else
                log.error("MQTT connect failed rc=%s", rc)
            )
            client.on_disconnect = lambda c, u, rc: (
                log.warning("MQTT disconnected rc=%s", rc) if rc != 0 else None
            )

            broker = mc.get("broker", "localhost")
            port = int(mc.get("port", 1883))
            keepalive = int(mc.get("keepalive", 60))

            try:
                client.connect(broker, port, keepalive)
                client.loop_start()
            except Exception as e:
                log.error("เชื่อมต่อ %s:%s ไม่สำเร็จ: %s", broker, port, e)
                self.client = None
                self._sig = None
                return None

            self.client = client
            self._sig = sig
            return self.client

    def publish(self, topic, payload, qos=0, retain=False):
        if self.client is None:
            return False
        try:
            r = self.client.publish(topic, payload, qos=qos, retain=retain)
            return r.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            log.error("publish '%s' ล้มเหลว: %s", topic, e)
            return False


# =====================================================================
#  Flask API fetcher
# =====================================================================
class FlaskSource:
    def __init__(self):
        self.base_url = "http://127.0.0.1:5000"

    def set_base_url(self, host, port):
        self.base_url = f"http://{host}:{port}"

    def fetch(self, endpoints):
        """ดึง endpoints ที่ต้องการ (dedup) คืน dict{ path: json }"""
        cache = {}
        for ep in set(endpoints):
            url = self.base_url + ep
            try:
                with urlopen(url, timeout=5) as resp:
                    cache[ep] = json.loads(resp.read().decode("utf-8"))
            except URLError as e:
                log.error("เรียก %s ไม่สำเร็จ (app.py รันอยู่ไหม?): %s", url, e)
                cache[ep] = None
            except Exception as e:
                log.error("ดึงข้อมูลจาก %s ผิดพลาด: %s", url, e)
                cache[ep] = None
        return cache


# =====================================================================
#  Main loop
# =====================================================================
def fmt(v):
    return round(v, 3) if isinstance(v, float) else v


def main():
    log.info("=== Phase 4 MQTT Publisher เริ่มต้น ===")
    log.info("Config: %s", CONFIG_PATH)

    cfg_mgr = ConfigManager(CONFIG_PATH)
    mqtt_mgr = MqttManager()
    source = FlaskSource()

    try:
        while True:
            cfg_mgr.reload()
            cfg = cfg_mgr.config

            if cfg is None:
                log.error("config ไม่พร้อม รออีก 10 วิ...")
                time.sleep(10)
                continue

            mc       = cfg.get("mqtt", {})
            fc       = cfg.get("flask", {})
            pc       = cfg.get("publish", {})
            channels = cfg.get("channels", [])
            topic    = cfg.get("topic", "jkbms/pi4/status")

            interval = int(pc.get("interval_seconds", 60))
            qos      = int(pc.get("qos", 0))
            retain   = bool(pc.get("retain", False))

            source.set_base_url(fc.get("host", "127.0.0.1"), fc.get("port", 5000))

            # ── เชื่อมต่อ MQTT ────────────────────────────────────
            client = mqtt_mgr.ensure_connected(mc)

            # ── รวบรวม endpoint ที่ active channels ต้องการ ───────
            active = [ch for ch in channels if ch.get("enable", True)]
            if not active:
                log.warning("ไม่มี channel ที่ enable อยู่ใน config")
                time.sleep(interval)
                continue

            # ── ดึงข้อมูลจาก Flask API ────────────────────────────
            cache = source.fetch([ch["api"] for ch in active])

            # ── ประกอบ JSON payload ───────────────────────────────
            payload = {"timestamp": int(time.time())}
            missing = []

            for ch in active:
                api   = ch.get("api", "")
                field = ch.get("field", "")
                key   = ch.get("key", field)
                data  = cache.get(api)

                if data is None:
                    missing.append(key)
                    continue

                value = data.get(field)
                if value is None:
                    missing.append(f"{key}(field '{field}' ไม่พบใน {api})")
                    continue

                payload[key] = fmt(value)

            if missing:
                log.warning("ค่าที่หายไป: %s", ", ".join(missing))

            # ── ส่ง JSON ก้อนเดียว ────────────────────────────────
            if client is None:
                log.error("MQTT ไม่ได้เชื่อมต่อ - ข้ามรอบนี้")
            elif len(payload) <= 1:  # มีแค่ timestamp ไม่มีข้อมูลจริง
                log.warning("ไม่มีข้อมูลส่ง - ข้ามรอบนี้")
            else:
                json_str = json.dumps(payload, ensure_ascii=False)
                if mqtt_mgr.publish(topic, json_str, qos=qos, retain=retain):
                    log.info("[%s] -> %s : %s",
                             time.strftime("%H:%M:%S"), topic, json_str)
                else:
                    log.error("ส่ง MQTT ไม่สำเร็จ")

            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("Ctrl+C -> ปิดโปรแกรม")
    finally:
        if mqtt_mgr.client:
            mqtt_mgr.client.loop_stop()
            mqtt_mgr.client.disconnect()


if __name__ == "__main__":
    main()
