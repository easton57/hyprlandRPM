# Package Build Order

This document defines the correct build order for all packages in this repository.
Packages are organized in tiers - each tier depends only on packages from previous tiers.

## Tier 0 - No internal dependencies (25 packages)

These can be built in any order:

1. hyprutils
2. hyprwayland-scanner
3. glaze
4. hyprland-protocols
5. aylurs-gtk-shell
6. xcur2png
7. uwsm
8. waybar-git
9. swww
10. swaylock-effects
11. satty
12. python-screeninfo
13. mpvpaper
14. python-imageio-ffmpeg
15. pyprland
16. matugen
17. kitty
18. material-icons-fonts
19. hyprnome
20. hellwal
21. hyprdim
22. eww-git
23. appmenu-glib-translator
24. astal-io
25. cliphist

## Tier 1 - Depends only on Tier 0 (10 packages)

26. hyprwire (needs: hyprutils)
27. hyprgraphics (needs: hyprutils)
28. hyprlang (needs: hyprutils)
29. aquamarine (needs: hyprutils, hyprwayland-scanner)
30. hyprpicker (needs: hyprutils, hyprwayland-scanner)
31. hyprqt6engine (needs: hyprlang, hyprutils)
32. hypridle (needs: hyprland-protocols, hyprlang, hyprutils, hyprwayland-scanner)
33. hyprsunset (needs: hyprland-protocols, hyprlang, hyprutils, hyprwayland-scanner)
34. nwg-look (needs: xcur2png)
35. hyprpolkitagent (needs: hyprutils)

## Tier 2 - Depends on Tier 1 (5 packages)

36. hyprcursor (needs: hyprlang)
37. hyprland-qt-support (needs: hyprlang)
38. hyprtoolkit (needs: hyprwayland-scanner, aquamarine, hyprgraphics, hyprlang, hyprutils)
39. xdg-desktop-portal-hyprland (needs: hyprland-protocols, hyprlang, hyprutils, hyprwayland-scanner)
40. hyprlock (needs: hyprwayland-scanner, hyprgraphics, hyprlang, hyprutils)

## Tier 3 - Depends on Tier 2 (6 packages)

41. hyprpaper (needs: hyprgraphics, hyprlang, hyprutils, hyprwayland-scanner, hyprtoolkit-devel, hyprwire-devel)
42. hyprsysteminfo (needs: hyprutils, hyprtoolkit, hyprland-qt-support)
43. hyprpwcenter (needs: hyprtoolkit, hyprutils)
44. hyprlauncher (needs: hyprlang, hyprtoolkit, hyprutils, hyprwire)
45. hyprland-guiutils (needs: hyprlang, hyprutils, hyprtoolkit)
46. nwg-clipman (needs: cliphist)

## Tier 4 - Depends on Tier 3 (3 packages)

47. hyprland-git (needs: aquamarine, hyprcursor, hyprgraphics, hyprlang, hyprutils, hyprwayland-scanner, hyprwire, glaze)
48. astal (needs: astal-io)
49. astal-gtk4 (needs: astal-io)

## Tier 5 - Astal bootstrapping (2 packages)

50. astal-libs (needs: astal, astal-io, appmenu-glib-translator)
51. astal-gjs (needs: astal, astal-io)

## Tier 6 - Final packages (3 packages)

52. astal-lua (needs: astal, astal-io)
53. hyprpanel (needs: aylurs-gtk-shell, astal-gjs)
54. waypaper (needs: swww - Recommends only)

## Tier 7 - Weak/recommended dependencies only (2 packages)

55. hyprshot (Recommends: hyprpicker)
56. hyprland-contrib (Recommends: hyprpicker via grimblast)

---

## Notes

- **Critical path**: hyprutils → hyprlang/hyprgraphics/aquamarine → hyprtoolkit → hyprland-git
- **Circular dependency**: astal ↔ astal-libs is resolved via bootstrap flag in astal-libs spec
- Packages within the same tier can be built in parallel
