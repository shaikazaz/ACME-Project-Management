"""Departments: everyone signed in may view them, admins manage them."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep, require
from app.auth.permissions import Permission
from app.errors import ApiError
from app.models import Department, User
from app.schemas.admin import DepartmentRequest, DepartmentResponse
from app.schemas.common import Page

router = APIRouter(prefix="/departments", tags=["departments"])

Admin = Annotated[User, Depends(require(Permission.MANAGE_DEPARTMENTS))]


def find_department(department_id: int, session: SessionDep, _: CurrentUser):
    """Load the department named in the path, or fail with 404."""
    department = session.get(Department, department_id)
    if department is None:
        raise ApiError(404, "Department not found.")
    return department


TargetDepartment = Annotated[Department, Depends(find_department)]


@router.get("")
def list_departments(session: SessionDep, _: CurrentUser) -> Page[DepartmentResponse]:
    """List all departments."""
    rows = session.scalars(select(Department).order_by(Department.name)).all()
    items = [DepartmentResponse.model_validate(row) for row in rows]
    return Page(items=items, total=len(items))


@router.get("/{department_id}")
def read_department(department: TargetDepartment) -> DepartmentResponse:
    """Return one department."""
    return DepartmentResponse.model_validate(department)


@router.post("", status_code=201)
def create_department(
    body: DepartmentRequest, _: Admin, session: SessionDep
) -> DepartmentResponse:
    """Create a department."""
    department = Department(**body.model_dump())
    session.add(department)
    session.commit()
    return DepartmentResponse.model_validate(department)


@router.put("/{department_id}")
def update_department(
    body: DepartmentRequest,
    _: Admin,
    department: TargetDepartment,
    session: SessionDep,
) -> DepartmentResponse:
    """Update a department."""
    department.name = body.name
    department.description = body.description
    session.commit()
    return DepartmentResponse.model_validate(department)


@router.delete("/{department_id}", status_code=204)
def delete_department(
    _: Admin, department: TargetDepartment, session: SessionDep
) -> None:
    """Delete a department that is not in use."""
    session.delete(department)
    session.commit()
