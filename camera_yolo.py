import requests
import cv2
import sqlite3
import numpy as np
import time
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
import csv
import os

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

FARMER_ID = os.getenv("VIKALP_FARMER_ID", "F001")
ROVER_ID = os.getenv("VIKALP_ROVER_ID", "R001")

BUCKET_NAME = "detection-images"


# ============================================================
# CHECK SUPABASE CONFIGURATION
# ============================================================

if not SUPABASE_URL:
    raise Exception("SUPABASE_URL not found in .env")

if not SUPABASE_SECRET_KEY:
    raise Exception("SUPABASE_SECRET_KEY not found in .env")


# ============================================================
# CONNECT TO SUPABASE
# ============================================================

print("Connecting to Supabase...")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)

print("Supabase connected successfully!")


# ============================================================
# SETTINGS
# ============================================================

ESP32_IP = "10.138.66.48"


# Leaf / Not-Leaf model
LEAF_GATE_MODEL = (
    r"C:\PlantDisease_YOLO\runs\classify\leaf_gate\weights\best.pt"
)


# Plant Disease model
DISEASE_MODEL = (
    r"C:\PlantDisease_YOLO\runs\classify\train\weights\best.pt"
)


# Main image storage
SAVE_DIR = Path(
    r"C:\PlantDisease_YOLO\camera_images"
)

SAVE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# CSV log
LOG_FILE = Path(
    r"C:\PlantDisease_YOLO\detection_log.csv"
)


# SQLite Database
DB_FILE = Path(
    r"C:\PlantDisease_YOLO\plant_disease.db"
)


# ============================================================
# SQLITE DATABASE
# ============================================================

conn = sqlite3.connect(DB_FILE)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    plant TEXT,
    disease TEXT,
    confidence REAL,
    status TEXT,
    image_path TEXT
)
""")

conn.commit()
conn.close()


# ============================================================
# CSV LOG FILE
# ============================================================

if not LOG_FILE.exists():

    with open(
        LOG_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "timestamp",
            "plant",
            "condition",
            "confidence",
            "status",
            "image_path"
        ])


# ============================================================
# CAPTURE SETTINGS
# ============================================================

CAPTURE_INTERVAL = 1

LEAF_THRESHOLD = 0.70

DISEASE_THRESHOLD = 0.60


# ============================================================
# LOAD MODELS
# ============================================================

print("==============================================")
print("       LIVE PLANT DISEASE MONITORING")
print("==============================================")
print()

print("Loading Leaf Gate model...")

leaf_model = YOLO(
    LEAF_GATE_MODEL
)

print("Leaf Gate loaded successfully!")

print()

print("Loading Plant Disease model...")

disease_model = YOLO(
    DISEASE_MODEL
)

print("Plant Disease model loaded successfully!")

print()

print("==============================================")
print("SYSTEM READY")
print("==============================================")
print("ESP32-CAM:", ESP32_IP)
print("Capture interval:", CAPTURE_INTERVAL, "seconds")
print("Farmer ID:", FARMER_ID)
print("Rover ID:", ROVER_ID)
print("Supabase bucket:", BUCKET_NAME)
print()
print("Press Q in the camera window to stop.")
print("==============================================")
print()


# ============================================================
# FUNCTION: SAVE TO LOCAL SQLITE DATABASE
# ============================================================

def save_to_database(
    plant,
    disease,
    confidence,
    status,
    detection_time,
    image_path
):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO detections
    (timestamp, plant, disease, confidence, status, image_path)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        detection_time,
        plant,
        disease,
        confidence,
        status,
        str(image_path)
    ))

    conn.commit()

    conn.close()

    print("Database update: SUCCESS")


# ============================================================
# FUNCTION: UPLOAD DETECTION TO SUPABASE
# ============================================================

def upload_to_supabase(
    plant,
    disease,
    confidence,
    status,
    detection_time,
    image_path
):

    try:

        print()
        print("Uploading detection to Supabase...")

        # ----------------------------------------------------
        # Create cloud filename
        # ----------------------------------------------------

        filename = image_path.name

        # ----------------------------------------------------
        # Cloud storage path
        # ----------------------------------------------------

        cloud_path = (
            f"{FARMER_ID}/"
            f"{ROVER_ID}/"
            f"{filename}"
        )

        # ----------------------------------------------------
        # Read local image
        # ----------------------------------------------------

        with open(
            image_path,
            "rb"
        ) as f:

            image_data = f.read()

        # ----------------------------------------------------
        # Upload image
        # ----------------------------------------------------

        supabase.storage.from_(
            BUCKET_NAME
        ).upload(
            cloud_path,
            image_data,
            {
                "content-type": "image/jpeg",
                "upsert": "true"
            }
        )

        print("Supabase image upload: SUCCESS")

        print(
            "Cloud path:",
            cloud_path
        )

        # ----------------------------------------------------
        # Prepare database record
        # ----------------------------------------------------

        cloud_record = {

            "timestamp": datetime.now().astimezone().isoformat(),

            "farmer_id": FARMER_ID,

            "rover_id": ROVER_ID,

            "plant": plant,

            "disease": disease,

            "confidence": float(confidence),

            "status": status,

            "image_path": cloud_path
        }

        # ----------------------------------------------------
        # Insert into Supabase PostgreSQL
        # ----------------------------------------------------

        supabase.table(
            "detections"
        ).insert(
            cloud_record
        ).execute()

        print(
            "Supabase database insert: SUCCESS"
        )

        print("----------------------------------------------")

    except Exception as e:

        # IMPORTANT:
        # Cloud failure must NOT stop local monitoring.

        print()
        print("----------------------------------------------")
        print("SUPABASE ERROR")
        print("----------------------------------------------")
        print(e)
        print("Local detection will continue.")
        print("----------------------------------------------")


# ============================================================
# FUNCTION: CAPTURE IMAGE
# ============================================================

def capture_image():

    url = f"http://{ESP32_IP}/capture"

    response = requests.get(
        url,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            f"Camera returned HTTP {response.status_code}"
        )

    image_array = np.frombuffer(
        response.content,
        dtype=np.uint8
    )

    frame = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if frame is None:

        raise Exception(
            "Could not decode camera image"
        )

    return frame


# ============================================================
# FUNCTION: SAFE FOLDER NAME
# ============================================================

def clean_name(name):

    invalid = '<>:"/\\|?*'

    for char in invalid:

        name = name.replace(
            char,
            "_"
        )

    return name.strip()


# ============================================================
# MAIN LIVE MONITORING LOOP
# ============================================================

try:

    while True:

        start_time = time.time()

        print()
        print("==============================================")
        print("CAPTURING IMAGE...")
        print("==============================================")

        try:

            frame = capture_image()

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            print(
                "Image captured:",
                timestamp
            )

        except Exception as e:

            print()
            print("CAMERA ERROR:", e)

            print(
                "Retrying in 5 seconds..."
            )

            time.sleep(5)

            continue


        # ====================================================
        # STEP 1: LEAF / NOT-LEAF GATE
        # ====================================================

        gate_result = leaf_model.predict(
            source=frame,
            imgsz=224,
            verbose=False
        )[0]

        gate_class = int(
            gate_result.probs.top1
        )

        gate_conf = float(
            gate_result.probs.top1conf
        )

        gate_prediction = gate_result.names[
            gate_class
        ]


        print()
        print("LEAF GATE")
        print("----------------------------------------------")
        print(
            "Prediction :",
            gate_prediction
        )
        print(
            "Confidence :",
            f"{gate_conf * 100:.2f}%"
        )


        # ====================================================
        # NOT A LEAF
        # ====================================================

        if (
            gate_prediction.lower() == "not_leaf"
            or gate_conf < LEAF_THRESHOLD
        ):

            print()
            print("❌ NOT A LEAF")
            print("Image ignored.")
            print(
                "It will NOT be sent to disease model."
            )

            display = frame.copy()

            cv2.putText(
                display,
                "NOT A LEAF - IGNORED",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2
            )

            cv2.putText(
                display,
                f"Gate Confidence: {gate_conf * 100:.1f}%",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            cv2.imshow(
                "Live Plant Monitoring",
                display
            )

            key = cv2.waitKey(1) & 0xFF

            if (
                key == ord("q")
                or key == ord("Q")
            ):
                break

            elapsed = time.time() - start_time

            if elapsed < CAPTURE_INTERVAL:

                time.sleep(
                    CAPTURE_INTERVAL - elapsed
                )

            continue


        # ====================================================
        # STEP 2: LEAF DETECTED
        # ====================================================

        print()
        print("✅ LEAF DETECTED")
        print("Sending image to disease model...")


        disease_result = disease_model.predict(
            source=frame,
            imgsz=224,
            verbose=False
        )[0]


        disease_class = int(
            disease_result.probs.top1
        )

        disease_conf = float(
            disease_result.probs.top1conf
        )

        disease_name = disease_result.names[
            disease_class
        ]


        print()
        print("PLANT DISEASE RESULT")
        print("----------------------------------------------")
        print(
            "Prediction :",
            disease_name
        )
        print(
            "Confidence :",
            f"{disease_conf * 100:.2f}%"
        )


        # ====================================================
        # LOW CONFIDENCE
        # ====================================================

        if disease_conf < DISEASE_THRESHOLD:

            print()
            print("⚠ LOW CONFIDENCE")
            print(
                "Disease result will NOT be categorized."
            )

            display = frame.copy()

            cv2.putText(
                display,
                "LOW CONFIDENCE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 165, 255),
                2
            )

            cv2.putText(
                display,
                f"{disease_name}",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2
            )

            cv2.putText(
                display,
                f"Confidence: {disease_conf * 100:.1f}%",
                (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2
            )

            cv2.imshow(
                "Live Plant Monitoring",
                display
            )

            key = cv2.waitKey(1) & 0xFF

            if (
                key == ord("q")
                or key == ord("Q")
            ):
                break

            elapsed = time.time() - start_time

            if elapsed < CAPTURE_INTERVAL:

                time.sleep(
                    CAPTURE_INTERVAL - elapsed
                )

            continue


        # ====================================================
        # STEP 3: SPLIT PLANT AND DISEASE
        # ====================================================

        if "___" in disease_name:

            parts = disease_name.split(
                "___",
                1
            )

            plant_name = parts[0]

            condition = parts[1]

        else:

            plant_name = "Unknown_Plant"

            condition = disease_name


        plant_name = clean_name(
            plant_name
        )

        condition = clean_name(
            condition
        )


        # ====================================================
        # STEP 4: HEALTHY / DISEASE STATUS
        # ====================================================

        if "healthy" in condition.lower():

            status = "HEALTHY"

        else:

            status = "DISEASE DETECTED"


        # ====================================================
        # STEP 5: CREATE SAVE FOLDER
        # ====================================================

        output_folder = (
            SAVE_DIR
            / plant_name
            / condition
        )

        output_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        # ====================================================
        # STEP 6: ANNOTATE IMAGE
        # ====================================================

        display = frame.copy()

        cv2.putText(
            display,
            f"Plant: {plant_name}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2
        )

        cv2.putText(
            display,
            f"Condition: {condition}",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2
        )

        cv2.putText(
            display,
            f"Confidence: {disease_conf * 100:.2f}%",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2
        )

        cv2.putText(
            display,
            status,
            (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )


        # ====================================================
        # STEP 7: SAVE IMAGE LOCALLY
        # ====================================================

        filename = (
            f"{timestamp}_"
            f"{plant_name}_"
            f"{condition}_"
            f"{disease_conf * 100:.1f}pct.jpg"
        )

        save_path = (
            output_folder
            / filename
        )

        cv2.imwrite(
            str(save_path),
            display
        )


        # ====================================================
        # STEP 8: LOCAL SQLITE DATABASE
        # ====================================================

        detection_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        confidence_percent = round(
            disease_conf * 100,
            2
        )

        save_to_database(
            plant_name,
            condition,
            confidence_percent,
            status,
            detection_time,
            save_path
        )


        # ====================================================
        # STEP 9: SUPABASE CLOUD
        # ====================================================

        upload_to_supabase(
            plant_name,
            condition,
            confidence_percent,
            status,
            detection_time,
            save_path
        )


        # ====================================================
        # STEP 10: FINAL RESULT
        # ====================================================

        print()
        print("==============================================")
        print("          FINAL RESULT")
        print("==============================================")
        print(
            "Plant       :",
            plant_name
        )
        print(
            "Condition   :",
            condition
        )
        print(
            "Confidence  :",
            f"{disease_conf * 100:.2f}%"
        )
        print(
            "Status      :",
            status
        )
        print(
            "Saved       :",
            save_path
        )
        print(
            "Farmer ID   :",
            FARMER_ID
        )
        print(
            "Rover ID    :",
            ROVER_ID
        )
        print("==============================================")


        # ====================================================
        # CSV LOG
        # ====================================================

        with open(
            LOG_FILE,
            "a",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.writer(f)

            writer.writerow([
                timestamp,
                plant_name,
                condition,
                f"{disease_conf * 100:.2f}%",
                status,
                str(save_path)
            ])


        # ====================================================
        # DISPLAY RESULT
        # ====================================================

        cv2.imshow(
            "Live Plant Monitoring",
            display
        )

        key = cv2.waitKey(1) & 0xFF

        if (
            key == ord("q")
            or key == ord("Q")
        ):
            break


        # ====================================================
        # WAIT BEFORE NEXT CAPTURE
        # ====================================================

        elapsed = time.time() - start_time

        if elapsed < CAPTURE_INTERVAL:

            time.sleep(
                CAPTURE_INTERVAL - elapsed
            )


except KeyboardInterrupt:

    print()
    print("Monitoring stopped by user.")


except Exception as e:

    print()
    print("SYSTEM ERROR:", e)


finally:

    cv2.destroyAllWindows()

    print()
    print("==============================================")
    print("LIVE MONITORING STOPPED")
    print("==============================================")