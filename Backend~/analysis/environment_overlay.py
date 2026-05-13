"""
Environment-Agnostic Scene Layout Overlay for VR Analytics Visualizations.

Reads scene_metadata.json (exported from ANY Unity scene) and provides
helper functions to draw the environment layout as a background on
matplotlib plots. Works with any scene — warehouse, factory, hospital, etc.

Usage:
    from environment_overlay import EnvironmentOverlay
    env = EnvironmentOverlay.auto_load()
    fig, ax = plt.subplots()
    env.draw_topdown(ax)
    # ... plot your data on top ...
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
from pathlib import Path
from typing import Optional, List, Dict, Tuple


class EnvironmentOverlay:
    """Environment-agnostic scene layout overlay for matplotlib plots."""

    def __init__(self, metadata: dict):
        self.metadata = metadata
        self.scene_name = metadata.get('scene_name', 'Unknown Scene')
        self.objects = metadata.get('objects', [])
        self.spatial_regions = metadata.get('spatial_regions', [])
        self.tagged_objects = metadata.get('tagged_objects', {})
        self.interactables = metadata.get('interactables', [])

        # Auto-detect environment structure
        self._floor = self._find_floor()
        self._walls = self._find_walls()
        self._obstacles = self._find_obstacles()
        self._zones = self._find_zones()
        self._equipment = self._find_equipment()

    # ── Factory methods ──────────────────────────────────────────
    @classmethod
    def auto_load(cls, search_dirs: Optional[List[str]] = None) -> 'EnvironmentOverlay':
        """Auto-detect and load scene_metadata.json from common locations."""
        if search_dirs is None:
            base = Path(__file__).parent
            search_dirs = [
                str(base),
                str(base / '..'),
                str(base / '..' / 'Assets' / 'Scripts'),
            ]
        for d in search_dirs:
            p = Path(d) / 'scene_metadata.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return cls(json.load(f))
        raise FileNotFoundError("scene_metadata.json not found in any search directory")

    @classmethod
    def from_file(cls, path: str) -> 'EnvironmentOverlay':
        with open(path, 'r', encoding='utf-8') as f:
            return cls(json.load(f))

    @classmethod
    def load_for_session(cls, session_dir: str, search_dirs: Optional[List[str]] = None) -> 'EnvironmentOverlay':
        """
        Load the correct environment overlay for a specific session.
        
        Reads session_info.json from the session folder to determine which scene
        was used, then loads the matching scene_metadata_{SceneName}.json file.
        Falls back to the default scene_metadata.json if no scene-specific file exists.
        
        Args:
            session_dir: Path to the session folder
            search_dirs: Optional list of directories to search for metadata files
            
        Returns:
            EnvironmentOverlay instance for the correct scene
        """
        if search_dirs is None:
            base = Path(session_dir)
            # Walk up to find the Data collection folder
            data_dir = base.parent if base.parent.name != 'Data collection' else base.parent
            while data_dir.name and data_dir.name != 'Data collection':
                data_dir = data_dir.parent
                if data_dir == data_dir.parent:  # reached root
                    data_dir = base.parent
                    break
            search_dirs = [str(data_dir), str(data_dir / '..')]
        
        # Try to determine scene name from session_info.json
        scene_name = None
        info_path = Path(session_dir) / 'session_info.json'
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                scene_name = info.get('scene_name', None)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Fallback: infer from filenames in session directory
        if not scene_name:
            try:
                import os
                for fname in os.listdir(session_dir):
                    fl = fname.lower()
                    if 'factory' in fl and 'performance' in fl:
                        scene_name = 'SmallFactory'
                        break
                    if 'warehouse' in fl and 'performance' in fl:
                        scene_name = 'FormalWarehouse'
                        break
            except OSError:
                pass
        
        # Try scene-specific metadata file first
        if scene_name:
            for d in search_dirs:
                p = Path(d) / f'scene_metadata_{scene_name}.json'
                if p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        return cls(json.load(f))
        
        # Fall back to default scene_metadata.json
        for d in search_dirs:
            p = Path(d) / 'scene_metadata.json'
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return cls(json.load(f))
        
        raise FileNotFoundError(
            f"No scene_metadata found for session '{session_dir}'"
            f"{f' (scene: {scene_name})' if scene_name else ''}")

    @classmethod
    def from_legacy_format(cls, path: str) -> 'EnvironmentOverlay':
        """Load from the old example_unity_environment.json format."""
        with open(path, 'r', encoding='utf-8') as f:
            legacy = json.load(f)

        # Convert legacy format to scene_metadata format
        objects = []
        spatial_regions = []

        if 'floor' in legacy:
            fl = legacy['floor']
            cx = (fl['x'][0] + fl['x'][1]) / 2
            cz = (fl['z'][0] + fl['z'][1]) / 2
            sx = fl['x'][1] - fl['x'][0]
            sz = fl['z'][1] - fl['z'][0]
            objects.append({
                'name': fl.get('name', 'Floor'),
                'path': 'Structure/Floor',
                'position': [cx, 0, cz],
                'tags': ['Ground'],
                'components': ['Transform', 'MeshFilter', 'MeshRenderer'],
                'bounds_size': [sx, 0.1, sz],
                'children': []
            })
            spatial_regions.append({
                'name': fl.get('name', 'Floor'),
                'center': [cx, 0, cz],
                'size': [sx, 0.1, sz]
            })

        for wall in legacy.get('walls', []):
            cx = (wall['x'][0] + wall['x'][1]) / 2
            cy = (wall['y'][0] + wall['y'][1]) / 2
            cz = (wall['z'][0] + wall['z'][1]) / 2
            sx = max(wall['x'][1] - wall['x'][0], 0.15)
            sy = wall['y'][1] - wall['y'][0]
            sz = max(wall['z'][1] - wall['z'][0], 0.15)
            objects.append({
                'name': wall.get('name', 'Wall'),
                'path': f"Structure/{wall.get('name', 'Wall')}",
                'position': [cx, cy, cz],
                'tags': ['Obstacle'],
                'components': ['Transform', 'MeshFilter', 'BoxCollider', 'MeshRenderer'],
                'bounds_size': [sx, sy, sz],
                'children': []
            })

        for shelf in legacy.get('shelves', []):
            cx = (shelf['x'][0] + shelf['x'][1]) / 2
            cy = (shelf['y'][0] + shelf['y'][1]) / 2
            cz = (shelf['z'][0] + shelf['z'][1]) / 2
            sx = shelf['x'][1] - shelf['x'][0]
            sy = shelf['y'][1] - shelf['y'][0]
            sz = shelf['z'][1] - shelf['z'][0]
            objects.append({
                'name': shelf.get('name', 'Shelf'),
                'path': f"Equipment/{shelf.get('name', 'Shelf')}",
                'position': [cx, cy, cz],
                'tags': [],
                'components': ['Transform', 'MeshFilter', 'MeshRenderer'],
                'bounds_size': [sx, sy, sz],
                'children': []
            })
            spatial_regions.append({
                'name': shelf.get('name', 'Shelf'),
                'center': [cx, cy, cz],
                'size': [sx, sy, sz]
            })

        metadata = {
            'scene_name': 'Legacy Scene',
            'objects': objects,
            'spatial_regions': spatial_regions,
            'tagged_objects': {},
            'interactables': []
        }
        return cls(metadata)

    # ── Auto-detection helpers ───────────────────────────────────
    def _find_floor(self) -> Optional[dict]:
        """Find the main floor object."""
        ground_tags = self.tagged_objects.get('Ground', [])
        # Prefer the largest ground-tagged object
        candidates = []
        for obj in self.objects:
            name_lower = obj['name'].lower()
            is_ground = obj['name'] in ground_tags or 'Ground' in obj.get('tags', [])
            # Identify floor objects generically — the area-based sorting below
            # ensures the largest floor wins, so we don't need scene-specific exclusions.
            is_floor_name = 'floor' in name_lower
            if (is_ground or is_floor_name) and obj.get('bounds_size'):
                bs = obj['bounds_size']
                area = bs[0] * bs[2]
                candidates.append((area, obj))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None

    def _find_walls(self) -> List[dict]:
        """Find wall objects."""
        walls = []
        obstacle_names = self.tagged_objects.get('Obstacle', [])
        for obj in self.objects:
            name_lower = obj['name'].lower()
            if 'wall' in name_lower and obj.get('bounds_size'):
                walls.append(obj)
        return walls

    def _find_obstacles(self) -> List[dict]:
        """Find obstacle objects (not walls)."""
        obstacles = []
        obstacle_names = self.tagged_objects.get('Obstacle', [])
        for obj in self.objects:
            if obj['name'] in obstacle_names and 'wall' not in obj['name'].lower():
                obstacles.append(obj)
        return obstacles

    def _find_zones(self) -> List[dict]:
        """Find zone/area markers."""
        zones = []
        for region in self.spatial_regions:
            name_lower = region['name'].lower()
            # Skip tiny regions, walls, and non-zone items
            if region['size'][0] < 1 or region['size'][2] < 1:
                continue
            if 'wall' in name_lower:
                continue
            # Skip boundary markers (BT_, BB_, BL_, BR_, L_)
            if any(region['name'].startswith(pfx) for pfx in ['BT_', 'BB_', 'BL_', 'BR_', 'L_']):
                continue
            # Skip the main floor (already drawn separately)
            if self._floor and region['name'] == self._floor['name']:
                continue
            zones.append(region)
        return zones

    def _find_equipment(self) -> List[dict]:
        """Find significant equipment/furniture objects to draw."""
        equipment = []
        # Look for objects with MeshRenderer and reasonable size
        skip_names = set()
        if self._floor:
            skip_names.add(self._floor['name'])
        for w in self._walls:
            skip_names.add(w['name'])

        for obj in self.objects:
            if obj['name'] in skip_names:
                continue
            if not obj.get('bounds_size'):
                continue
            bs = obj['bounds_size']
            # Must be reasonably sized (not tiny parts, not huge floors)
            area = bs[0] * bs[2]
            if area < 0.5 or area > 100:
                continue
            # Must have a renderer
            if 'MeshRenderer' not in obj.get('components', []):
                continue
            # Skip zone floor markers
            name_lower = obj['name'].lower()
            if name_lower.startswith('f_') or name_lower.startswith('bt_') or name_lower.startswith('bb_'):
                continue
            if name_lower.startswith('bl_') or name_lower.startswith('br_') or name_lower.startswith('l_'):
                continue
            # Skip sub-parts of conveyor belts etc (names like 04_bolt, 05_gear)
            if any(c.isdigit() for c in obj['name'][:3]) and '_' in obj['name'][:4]:
                continue
            equipment.append(obj)
        return equipment

    # ── Bounds computation ───────────────────────────────────────
    def get_floor_bounds(self) -> Tuple[float, float, float, float]:
        """Return (x_min, x_max, z_min, z_max) of the floor."""
        if self._floor and self._floor.get('bounds_size'):
            pos = self._floor['position']
            bs = self._floor['bounds_size']
            return (
                pos[0] - bs[0] / 2, pos[0] + bs[0] / 2,
                pos[2] - bs[2] / 2, pos[2] + bs[2] / 2
            )
        # Fallback: compute from all objects
        xs, zs = [], []
        for obj in self.objects:
            if obj.get('position'):
                xs.append(obj['position'][0])
                zs.append(obj['position'][2])
        if xs:
            margin = 2
            return (min(xs) - margin, max(xs) + margin, min(zs) - margin, max(zs) + margin)
        return (-15, 15, -15, 15)

    def get_wall_height(self) -> float:
        """Return the height of the walls."""
        for w in self._walls:
            if w.get('bounds_size'):
                return w['bounds_size'][1]
        return 4.0

    # ── Drawing methods ──────────────────────────────────────────
    def draw_topdown(self, ax, alpha: float = 0.15, show_zones: bool = True,
                     show_equipment: bool = True, show_labels: bool = True,
                     zone_alpha: float = 0.08, equipment_alpha: float = 0.3):
        """Draw the environment layout as a top-down overlay on the given axes."""
        x_min, x_max, z_min, z_max = self.get_floor_bounds()

        # Floor
        floor_rect = Rectangle(
            (x_min, z_min), x_max - x_min, z_max - z_min,
            linewidth=2, edgecolor='#888888', facecolor='#e8e8e8',
            alpha=alpha, zorder=0, label='Floor'
        )
        ax.add_patch(floor_rect)

        # Walls
        for wall in self._walls:
            if not wall.get('bounds_size'):
                continue
            pos = wall['position']
            bs = wall['bounds_size']
            rect = Rectangle(
                (pos[0] - bs[0] / 2, pos[2] - bs[2] / 2),
                bs[0], bs[2],
                linewidth=2, edgecolor='#666666', facecolor='#999999',
                alpha=0.4, zorder=1
            )
            ax.add_patch(rect)

        # Zones
        if show_zones:
            zone_colors = plt.cm.Set3(np.linspace(0, 1, max(len(self._zones), 1)))
            for i, zone in enumerate(self._zones):
                pos = zone['center']
                sz = zone['size']
                # Skip zones with zero or near-zero height (floor markers)
                if sz[1] < 0.05 and sz[0] > 2 and sz[2] > 2:
                    rect = Rectangle(
                        (pos[0] - sz[0] / 2, pos[2] - sz[2] / 2),
                        sz[0], sz[2],
                        linewidth=1, edgecolor=zone_colors[i % len(zone_colors)],
                        facecolor=zone_colors[i % len(zone_colors)],
                        alpha=zone_alpha, zorder=1, linestyle='--'
                    )
                    ax.add_patch(rect)
                    if show_labels:
                        label = zone['name'].replace('F_', '').replace('Zone_', '')
                        # Wrap long labels
                        if len(label) > 15:
                            parts = label.split('_')
                            label = '\n'.join(parts)
                        ax.text(pos[0], pos[2], label, ha='center', va='center',
                                fontsize=6, color='#555555', alpha=0.7, zorder=2)

        # Equipment / obstacles
        if show_equipment:
            for obj in self._equipment:
                pos = obj['position']
                bs = obj['bounds_size']
                color = '#8B7355' if bs[1] > 0.5 else '#A0A0A0'
                rect = FancyBboxPatch(
                    (pos[0] - bs[0] / 2, pos[2] - bs[2] / 2),
                    bs[0], bs[2],
                    boxstyle="round,pad=0.02",
                    linewidth=0.5, edgecolor='#666666', facecolor=color,
                    alpha=equipment_alpha, zorder=2
                )
                ax.add_patch(rect)
                if show_labels and (bs[0] * bs[2]) > 1.0:
                    label = obj['name']
                    if len(label) > 12:
                        label = label[:10] + '..'
                    ax.text(pos[0], pos[2], label, ha='center', va='center',
                            fontsize=5, color='white', fontweight='bold', alpha=0.8, zorder=3)

        # Set axis limits with margin
        margin = 1.5
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(z_min - margin, z_max + margin)
        ax.set_xlabel('X Position (m)')
        ax.set_ylabel('Z Position (m)')
        ax.set_aspect('equal')

    def draw_topdown_3d(self, ax, alpha: float = 0.15):
        """Draw the environment layout on a 3D axes (floor + walls as surfaces)."""
        x_min, x_max, z_min, z_max = self.get_floor_bounds()
        wall_h = self.get_wall_height()

        # Floor plane
        xx = np.array([[x_min, x_max], [x_min, x_max]])
        zz = np.array([[z_min, z_min], [z_max, z_max]])
        yy = np.zeros_like(xx)
        ax.plot_surface(xx, zz, yy, alpha=alpha * 0.5, color='lightgray', zorder=0)

        # Walls as transparent surfaces
        for wall in self._walls:
            if not wall.get('bounds_size'):
                continue
            pos = wall['position']
            bs = wall['bounds_size']
            # Determine if wall is along X or Z axis
            if bs[0] > bs[2]:  # Wall along X
                wx = np.array([[pos[0] - bs[0] / 2, pos[0] + bs[0] / 2],
                               [pos[0] - bs[0] / 2, pos[0] + bs[0] / 2]])
                wz = np.array([[pos[2], pos[2]], [pos[2], pos[2]]])
                wy = np.array([[0, 0], [wall_h, wall_h]])
            else:  # Wall along Z
                wx = np.array([[pos[0], pos[0]], [pos[0], pos[0]]])
                wz = np.array([[pos[2] - bs[2] / 2, pos[2] + bs[2] / 2],
                               [pos[2] - bs[2] / 2, pos[2] + bs[2] / 2]])
                wy = np.array([[0, 0], [wall_h, wall_h]])
            ax.plot_surface(wx, wz, wy, alpha=alpha * 0.3, color='gray', zorder=0)

        # Equipment as 3D boxes
        for obj in self._equipment[:15]:  # Limit to avoid clutter
            pos = obj['position']
            bs = obj['bounds_size']
            if bs[0] * bs[2] < 0.5:
                continue
            # Draw as a box outline
            x0, x1 = pos[0] - bs[0] / 2, pos[0] + bs[0] / 2
            z0, z1 = pos[2] - bs[2] / 2, pos[2] + bs[2] / 2
            y0, y1 = 0, min(bs[1], wall_h)
            # Top face
            bx = np.array([[x0, x1], [x0, x1]])
            bz = np.array([[z0, z0], [z1, z1]])
            by = np.full_like(bx, y1)
            ax.plot_surface(bx, bz, by, alpha=alpha * 0.8, color='#8B7355', zorder=1)

        ax.set_xlabel('X (m)')
        ax.set_ylabel('Z (m)')
        ax.set_zlabel('Y (m)')
        ax.set_xlim(x_min - 1, x_max + 1)
        ax.set_ylim(z_min - 1, z_max + 1)
        ax.set_zlim(0, wall_h + 0.5)

    def draw_heatmap_background(self, ax, alpha: float = 0.1):
        """Draw a minimal background for heatmap overlays (just floor outline + walls)."""
        x_min, x_max, z_min, z_max = self.get_floor_bounds()

        # Floor outline only
        floor_rect = Rectangle(
            (x_min, z_min), x_max - x_min, z_max - z_min,
            linewidth=2, edgecolor='#888888', facecolor='none',
            alpha=0.3, zorder=0
        )
        ax.add_patch(floor_rect)

        # Equipment outlines
        for obj in self._equipment:
            pos = obj['position']
            bs = obj['bounds_size']
            if bs[0] * bs[2] < 0.5:
                continue
            rect = Rectangle(
                (pos[0] - bs[0] / 2, pos[2] - bs[2] / 2),
                bs[0], bs[2],
                linewidth=0.5, edgecolor='#999999', facecolor='none',
                alpha=0.3, zorder=1
            )
            ax.add_patch(rect)

        margin = 1.5
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(z_min - margin, z_max + margin)
        ax.set_aspect('equal')

    # ── Utility ──────────────────────────────────────────────────
    def get_zone_at_position(self, x: float, z: float) -> Optional[str]:
        """Return the zone name at a given (x, z) position, or None."""
        for zone in self._zones:
            pos = zone['center']
            sz = zone['size']
            if (abs(x - pos[0]) <= sz[0] / 2 and abs(z - pos[2]) <= sz[2] / 2):
                return zone['name']
        return None

    def __repr__(self):
        return (f"EnvironmentOverlay(scene='{self.scene_name}', "
                f"floor={'yes' if self._floor else 'no'}, "
                f"walls={len(self._walls)}, zones={len(self._zones)}, "
                f"equipment={len(self._equipment)})")
