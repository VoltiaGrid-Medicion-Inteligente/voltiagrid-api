from fastapi import APIRouter, Depends
from app.api.customer_consumption.security import get_current_user
from app.api.customer_consumption.service import get_daily_consumption

router = APIRouter(prefix="/customers", tags=["Consumption"])

@router.get("/{customer_id}/consumption/daily")
def read_daily_consumption(customer_id: str, month: str, current_user: dict = Depends(get_current_user)):
    """
    Returns a customer's daily consumption per band for a month, 
    including the estimated-readings flag.
    """
    return get_daily_consumption(
        current_user=current_user,
        target_customer_id=customer_id,
        month=month
    )