import sqlite3

from fastapi import APIRouter, Depends

from api.deps import get_db
from api.schemas.common import DateStr
from api.schemas.distributions import (
    DistributionDetailOut,
    DistributionListOut,
    UndistributedProfitOut,
)
from db.distributions import (
    get_profit_distribution,
    get_undistributed_profit,
    list_profit_distributions,
)
from db.errors import NotFoundError

router = APIRouter(tags=["distributions"])


@router.get("/distributions", response_model=list[DistributionListOut])
def read_distributions(
    start_date: DateStr | None = None,
    end_date: DateStr | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[DistributionListOut]:
    distributions = list_profit_distributions(
        conn, start_date=start_date, end_date=end_date
    )
    return [DistributionListOut.model_validate(d) for d in distributions]


# Registered before /distributions/{distribution_id} so "undistributed" is
# never treated as a distribution id; distribution_id is also typed as int
# below, belt-and-suspenders.
@router.get("/distributions/undistributed", response_model=UndistributedProfitOut)
def read_undistributed_profit(
    as_of: DateStr, conn: sqlite3.Connection = Depends(get_db)
) -> UndistributedProfitOut:
    undistributed_profit = get_undistributed_profit(conn, as_of)
    return UndistributedProfitOut(undistributed_profit=undistributed_profit, as_of=as_of)


@router.get("/distributions/{distribution_id}", response_model=DistributionDetailOut)
def read_distribution(
    distribution_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> DistributionDetailOut:
    distribution = get_profit_distribution(conn, distribution_id)
    if distribution is None:
        raise NotFoundError(f"Distribution with id {distribution_id} does not exist")
    return DistributionDetailOut.model_validate(distribution)
