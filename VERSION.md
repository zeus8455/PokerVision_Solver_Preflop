# Version history

## V0.2.0
Clear_JSON adapter hardening and synthetic preflop cases:
- chips:false is treated as 0bb committed
- absent all_in is treated as False
- all_in:true requires numeric chips
- folded players remain parsed but inactive
- sitout players, if present, are excluded from active hand state
- already clicked Clear_JSON is rejected as solver input
- hero validation tightened
- synthetic tests added for Clear_JSON edge cases

## V0.1.1
Removed Python cache artifacts from Git.

## V0.1.0
Initial skeleton:
- contracts
- cards
- Clear_JSON adapter
- basic spot classifier
- sizing policy
- decision engine stub for BB option vs limp / unopened / fallback
- CLI solve_clear_json.py
