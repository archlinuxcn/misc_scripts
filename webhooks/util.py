from __future__ import annotations

from typing import (
  List, Literal, Optional, NamedTuple,
  NewType,
)

Maintainer = NewType('Maintainer', str)

def annotate_maints(
  pkg: str, maints: List[Maintainer],
) -> str:
  maints_str = ', '.join(f'@{m}' for m in maints)
  return f'{pkg} ({maints_str})'

class Dependent(NamedTuple):
  pkgbase: str
  maintainers: List[Maintainer]

class OrphanResult:
  _lit_created = False

  def __new__(
    cls,
    ty: Literal['Removed', 'NotFound', 'Depended'],
    dependents: Optional[List[Dependent]] = None,
  ) -> OrphanResult:
    if ty in ['Removed', 'NotFound'] and \
       cls._lit_created:
      return getattr(cls, ty)

    inst = super().__new__(cls)
    inst.__init__(ty, dependents)
    return inst

  def __init__(
    self,
    ty: Literal['Removed', 'NotFound', 'Depended'],
    dependents: Optional[List[Dependent]] = None,
  ) -> None:
    self.ty = ty
    if ty == 'Depended':
      if dependents is None:
        raise ValueError('dependents not given')
      self.dependents = dependents

  @classmethod
  def Depended(
    cls, dependents: List[Dependent],
  ) -> OrphanResult:
    return cls('Depended', dependents)

  def __repr__(self) -> str:
    name = self.__class__.__name__
    if self.ty == 'Depended':
      s = f'<{name}: Depended({self.dependents!r})>'
    else:
      s = f'<{name}: {self.ty}>'
    return s

  Removed: OrphanResult
  NotFound: OrphanResult

OrphanResult.Removed = OrphanResult('Removed')
OrphanResult.NotFound = OrphanResult('NotFound')
OrphanResult._lit_created = True

