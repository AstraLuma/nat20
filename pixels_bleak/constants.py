import bleak

SERVICE_PIXELS = bleak.uuids.normalize_uuid_str(
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
)
SERVICE_INFO = bleak.uuids.normalize_uuid_str('180a')

CHARI_NOTIFY = bleak.uuids.normalize_uuid_str(
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e")

CHARI_WRITE = bleak.uuids.normalize_uuid_str(
    "6e400002-b5a3-f393-e0a9-e50e24dcca9e")

bleak.uuids.register_uuids({
    SERVICE_PIXELS: "Pixels Dice Communications Service",
    CHARI_NOTIFY: "Pixels Dice Notify Characiteristic",
    CHARI_WRITE: "Pixels Dice Write Characiteristic",
})
