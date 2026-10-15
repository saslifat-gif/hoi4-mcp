"""Resolve native save paths within the protected user profile's write root."""
from pathlib import Path

def owned_save_path(user_root,native_path,basename):
 user=Path(user_root).resolve();owned=(user/'save games').resolve();path=Path(native_path)
 if '..' in path.parts:raise ValueError('Save traversal refused')
 if not path.is_absolute():
  if not path.parts or path.parts[0]!='save games':raise ValueError('Native save path outside user save root')
  path=user/path
 path=path.resolve();path.relative_to(owned)
 if path.name!=basename+'.hoi4':raise ValueError('Save filename differs from owned basename')
 return path
