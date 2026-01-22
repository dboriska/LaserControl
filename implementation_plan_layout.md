# Live Layout Redesign Plan

## Objective
Maximize the size of the Live Plot by moving controls from the top to a side panel.

## Proposed Layout

**Current Interface (Vertical Stack):**
```
[ Laser Controls (Horizontal) ]
[ Scope Controls (Horizontal) ]
[       PLOT AREA             ]
```

**New Interface (Horizontal Split):**
```
[                         ] [ Control Panel (Vertical) ]
[                         ] [ - Laser Controls Group   ]
[       PLOT AREA         ] [   - Power                ]
[      (Expands)          ] [   - Wavelength           ]
[                         ] [   - Tuning Step          ]
[                         ] [ - Scope Controls Group   ]
[                         ] [   - Start/Stop           ]
[                         ] [   - Auto Scale           ]
```

## Implementation Details

### `src/laser_control/gui/widgets/live_plot.py`

1.  **`setup_laser_controls`**:
    *   Change root layout from `QHBoxLayout` to `QVBoxLayout` to stack controls vertically.
    *   Remove the horizontal separator `QFrame.VLine` (maybe replace with `HLine` or remove).
    *   Organize "Power" and "Wavelength" into tidier vertical groups.

2.  **`setup_ui`**:
    *   Change root layout to `QHBoxLayout`.
    *   **Add Plot** first (Left side, `stretch=1`).
    *   **Add Control Panel** second (Right side, `stretch=0`).
        *   The Control Panel will contain the `laser_controls` GroupBox.
        *   It will also contain the Scope Controls (Start/Stop buttons), moved from the separate HBox.

## Verification
*   **Manual Test**: Run the app (`uv run laser-control`), check "Live Mode".
*   **Success Criteria**: The plot should occupy the full height of the tab. Controls should be neatly stacked on the right.
