import csv
from codecs import iterdecode
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import Depends, FastAPI, File, UploadFile, status, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import Base, engine, get_db
from models import Ingredient
from typing import Optional, List

UPLOAD_DIR = Path('uploads')
UPLOAD_DIR.mkdir(exist_ok=True)

Base.metadata.create_all(engine)

app = FastAPI(title='냉장고 관리 API')

class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, description="식재료 이름")
    category: str = Field(default="미분류", description="카테고리")
    quantity: str = Field(default="1", description="수량")
    expiration_date: Optional[str] = Field(default=None, description="유통기한 (YYYY-MM-DD)")

# [추가] 조회 결과 포맷을 정의하는 Pydantic 모델을 여기에 명시해야 에러가 나지 않습니다.
class IngredientResponse(BaseModel):
    id: int
    name: str
    category: str
    quantity: Optional[str] = None
    purchase_date: str
    expiration_date: str
    stroage_method: str

    class Config:
        from_attributes = True  # SQLAlchemy 객체를 Pydantic 변수로 자동 매핑해 주는 옵션

@app.post("/ingredients/upload", status_code=status.HTTP_201_CREATED, summary="CSV 파일을 통한 식재료 데이터")
async def upload_ingredients_csv(
    file: UploadFile = File(..., description="식재료 CSV 파일"),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="csv 파일만 업로드 가능합니다."
        )

    try:
        decoded = iterdecode(file.file, 'utf-8-sig')
        csv_reader = csv.DictReader(decoded)
        
        ingredients_to_insert = []
        
        for row in csv_reader:
            name = row.get("식재료")
            if not name:
                continue
                
            category = row.get("분류", "미분류")
            quantity = row.get("수량", "1")
            
            # [수정 1] CSV의 '구매일' 헤더에서 데이터를 올바르게 추출 (기본값 제공)
            purchase_date = row.get("구매일", "2026-08-24")
            
            # [수정 2] CSV의 실제 헤더 명칭인 '보관'으로 변경
            stroage_method = row.get("보관", "냉장") 
            
            raw_expiration = row.get("유통기한")
            expiration_date = "2026-12-31"
            
            if raw_expiration and '/' in raw_expiration:
                parts = [p.strip() for p in raw_expiration.split('/')]
                if len(parts) == 2:
                    try:
                        month = int(parts[0])
                        day = int(parts[1])
                        expiration_date = f"2026-{month:02d}-{day:02d}"
                    except ValueError:
                        pass

            # [수정 3] models.py의 스키마 제약조건(NOT NULL)에 맞춰 모든 필드를 정확히 채워줌
            db_ingredient = Ingredient(
                name=name,
                category=category,
                quantity=quantity,
                purchase_date=purchase_date,       # 필수 필드 누락 해결!
                expiration_date=expiration_date,
                stroage_method=stroage_method      # 오타 명칭 유지하여 매핑 성공!
            )
            ingredients_to_insert.append(db_ingredient)

        # [수정 4] FOR 루프 외부에서 안전하게 대량 적재 및 단일 커밋 실행
        success_count = len(ingredients_to_insert)
        if success_count > 0:
            db.add_all(ingredients_to_insert)
            db.commit()
            return {"message": f"성공적으로 {success_count}개의 식재료 데이터를 적재했습니다."}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="적재할 유효한 데이터가 파일에 없습니다."
            )

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"데이터 적재 중 오류가 발생했습니다: {str(e)}"
        )

@app.get("/ingredients", response_model=List[IngredientResponse], summary="식재료 목록 조회")
async def list_ingredients(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    저장된 모든 식재료 목록을 가져옵니다. 
    쿼리 파라미터로 특정 카테고리를 지정하면 해당 카테고리만 필터링합니다.
    """
    try:
        # SQLAlchemy 2.0 select 구문 사용
        stmt = select(Ingredient)
        
        # 카테고리 필터링 조건이 있는 경우 추가
        if category:
            stmt = stmt.where(Ingredient.category == category)
            
        # ID 순서대로 정렬하여 가져오기
        stmt = stmt.order_by(Ingredient.id)
        
        result = db.execute(stmt)
        ingredients = result.scalars().all()
        return ingredients
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"데이터 조회 중 오류가 발생했습니다: {str(e)}"
        )
