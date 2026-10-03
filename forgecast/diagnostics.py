"""Shared Stream Doctor sensitivity presets (seconds and recent frame ratios)."""
PROFILES = {
    'sensitive': {'wait':3, 'clear':5, 'ratio':0.005},
    'balanced': {'wait':8, 'clear':10, 'ratio':0.01},
    'relaxed': {'wait':15, 'clear':15, 'ratio':0.02},
}


def policy(name):
    if not isinstance(name, str) or name not in PROFILES: raise ValueError('Choose Sensitive, Balanced or Relaxed.')
    return PROFILES[name]
