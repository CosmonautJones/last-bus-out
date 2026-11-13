"""Small geometry helpers (no GIS stack needed)."""
import numpy as np

EARTH_R = 6_371_000.0


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters. Works on scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def walk_seconds(dist_m, speed_mps: float, detour: float):
    return dist_m * detour / speed_mps
