# Troubleshooting

## 냉장고 식재료 관리 프로젝트 문제 해결 기록

프로젝트를 진행하면서 발생한 주요 오류와 문제의 원인, 해결 방법을 정리하였다.

---

## 1. PostgreSQL 테이블과 SQLAlchemy 모델의 필드명 불일치

### 문제

초기 SQLAlchemy 모델에서 보관방법 필드명을 다음과 같이 작성하였다.

```python id="5x55d5"
stroage_method
```

`storage`의 철자가 잘못되어 이후 API 및 Streamlit에서 사용하는 필드명과 일치하지 않는 문제가 발생하였다.

### 원인

초기 데이터베이스 모델 작성 과정에서 `storage_method`를 `stroage_method`로 잘못 작성하였다.

### 해결

프로젝트의 필드명을 다음과 같이 통일하였다.

```python id="o7lv45"
storage_method
```

SQLAlchemy 모델, Pydantic Schema, FastAPI API, Streamlit에서 모두 동일한 필드명을 사용하도록 수정하였다.

### 결과

데이터베이스와 API 사이에서 보관방법 데이터를 정상적으로 전달할 수 있게 되었다.

---

## 2. CSV 파일의 컬럼명과 데이터베이스 필드 매핑 문제

### 문제

CSV 파일의 컬럼명과 SQLAlchemy 모델의 필드명이 서로 달라 CSV 데이터를 정상적으로 저장하기 어려웠다.

CSV에서는 다음과 같은 한글 컬럼명을 사용하였다.

```text id="3mw5y1"
식재료
분류
수량
구매일
유통기한
보관
```

반면 SQLAlchemy 모델에서는 다음과 같은 영문 필드명을 사용하였다.

```text id="r42s16"
name
category
quantity
purchase_date
expiration_date
storage_method
```

### 원인

CSV 파일은 사용자가 쉽게 이해할 수 있도록 한글 컬럼명을 사용하고 있었지만 데이터베이스 모델은 영문 변수명을 사용하고 있었기 때문이다.

### 해결

CSV 데이터를 읽을 때 각 컬럼을 SQLAlchemy 모델의 필드에 직접 매핑하였다.

```python id="kak2ts"
name = row.get("식재료")
category = row.get("분류", "미분류")
quantity = row.get("수량", "1")
storage_method = row.get("보관", "냉장")
```

### 결과

CSV의 한글 컬럼을 유지하면서 PostgreSQL의 `ingredients` 테이블에 정상적으로 데이터를 저장할 수 있게 되었다.

---

## 3. 구매일 및 유통기한 날짜 처리 문제

### 문제

초기 모델에서는 구매일과 유통기한을 문자열로 처리하였다.

하지만 날짜 비교와 유통기한 계산 기능을 구현하면서 문자열보다 날짜 자료형을 사용하는 것이 필요하였다.

### 해결

SQLAlchemy 모델에서 다음과 같이 `Date` 타입으로 변경하였다.

```python id="8el1bs"
purchase_date: Mapped[date] = mapped_column(Date)
expiration_date: Mapped[date] = mapped_column(Date, index=True)
```

Pydantic Schema에서도 `date` 타입을 사용하도록 수정하였다.

### 결과

FastAPI에서 날짜 데이터 검증이 가능해졌으며 Streamlit에서 오늘 날짜와 유통기한을 비교하여 남은 일수를 계산할 수 있게 되었다.

이를 활용하여 다음과 같이 식재료를 구분하였다.

* 유통기한 만료
* 오늘까지
* 1~3일 남음
* 4~7일 남음
* 8일 이상

---

## 4. CSV의 날짜 형식 변환 문제

### 문제

CSV 데이터의 날짜가 다음과 같이 입력되어 있었다.

```text id="cvxfs7"
8/25
9/1
12/31
```

하지만 데이터베이스에서는 날짜를 `YYYY-MM-DD` 형식으로 처리해야 했다.

### 해결

`parse_date()` 함수를 만들어 `M/D` 형식의 문자열을 `YYYY-MM-DD` 형식으로 변환하였다.

예:

```text id="ejp88x"
8/25 → 2026-08-25
9/1  → 2026-09-01
```

날짜 형식이 잘못되거나 필수 날짜가 없는 데이터는 등록하지 않고 건너뛰도록 처리하였다.

### 결과

CSV 파일에 입력된 날짜 데이터를 PostgreSQL의 `Date` 타입에 정상적으로 저장할 수 있게 되었다.

---

## 5. 필수값 누락으로 인한 데이터 적재 오류

### 문제

CSV 데이터를 데이터베이스에 저장하는 과정에서 테이블의 필수 컬럼에 값이 들어가지 않으면 데이터 적재가 실패하는 문제가 발생하였다.

### 원인

PostgreSQL의 NOT NULL 제약조건이 적용된 필드에 필요한 값이 전달되지 않았기 때문이다.

### 해결

CSV의 구매일과 유통기한을 확인하고 정상적인 날짜로 변환된 데이터만 `Ingredient` 객체로 생성하였다.

잘못된 행은 `skipped_rows`로 계산하여 건너뛰도록 처리하였다.

### 결과

잘못된 데이터 하나 때문에 전체 CSV 등록이 실패하는 문제를 줄이고 정상적인 데이터만 저장할 수 있게 되었다.

---

## 6. FastAPI main.py가 길어지는 문제

### 문제

초기에는 데이터베이스 처리, Schema, API 엔드포인트 등의 코드가 `main.py`에 함께 작성되어 있었다.

기능이 증가하면서 코드가 길어지고 유지보수가 어려워졌다.

### 해결

기능별로 파일을 분리하였다.

```text id="jy6j2d"
main.py
database.py
models.py

routers/
└── ingredient.py

schema/
├── request.py
└── response.py
```

`main.py`에서는 FastAPI 애플리케이션 생성과 Router 등록을 담당하도록 단순화하였다.

### 결과

각 파일의 역할이 명확해졌으며 API 기능을 수정하거나 추가하기 쉬운 구조가 되었다.

---

## 7. 식재료 수정 시 전체 데이터를 다시 보내야 하는 문제

### 문제

식재료의 수량이나 유통기한처럼 일부 정보만 수정하고 싶은 경우에도 전체 데이터를 다시 전달하면 사용하기 불편하였다.

### 해결

수정 API에 `PATCH` 방식을 적용하였다.

`IngredientUpdate`의 필드를 Optional로 정의하고 다음 코드를 사용하였다.

```python id="f9u42h"
update_data = body.model_dump(exclude_unset=True)
```

전달된 필드만 추출한 후 `setattr()`을 사용하여 변경된 항목만 수정하였다.

### 결과

식재료 정보 중 필요한 항목만 선택하여 수정할 수 있게 되었다.

---

## 8. 존재하지 않는 식재료 ID 요청 처리

### 문제

존재하지 않는 식재료 ID를 조회·수정·삭제할 경우 적절한 오류 처리가 필요하였다.

### 해결

공통 조회 함수 `get_ingredient_or_404()`를 구현하였다.

식재료가 존재하지 않으면 다음 HTTP 상태 코드를 반환하도록 하였다.

```text id="ay73o8"
404 Not Found
```

### 결과

조회, 수정, 삭제 API에서 동일한 방식으로 존재하지 않는 데이터에 대한 예외를 처리할 수 있게 되었다.

---

## 9. 많은 식재료 데이터를 한 화면에 표시하는 문제

### 문제

등록된 식재료가 많아질 경우 전체 데이터를 한 화면에 표시하면 목록을 확인하기 불편하였다.

### 해결

FastAPI에서는 `skip`, `limit`을 이용한 페이지네이션을 구현하였다.

Streamlit에서는 한 페이지에 20개의 식재료를 표시하고 이전·다음 및 페이지 번호 버튼을 이용하여 이동하도록 구현하였다.

### 결과

데이터가 많아져도 식재료 목록을 편리하게 확인할 수 있게 되었다.

---

## 10. Streamlit과 FastAPI 서버 연결 문제 대응

### 문제

Streamlit을 먼저 실행하거나 FastAPI 서버가 실행되지 않은 경우 API 요청에 실패할 수 있었다.

### 해결

Streamlit 실행 시 FastAPI 기본 엔드포인트에 요청하여 서버 연결 상태를 확인하도록 구현하였다.

연결 상태를 사이드바에 다음과 같이 표시하였다.

```text id="ykc5ie"
API 연결됨
API 연결 실패
```

또한 요청 과정에서 ConnectionError, Timeout, RequestException 등을 처리하도록 구성하였다.

### 결과

FastAPI 서버가 실행되지 않은 경우에도 프로그램이 바로 중단되지 않고 사용자에게 서버 연결 상태와 오류 내용을 안내할 수 있게 되었다.

---

# 문제 해결을 통해 배운 점

이번 프로젝트에서는 단순히 API 기능을 구현하는 것뿐만 아니라 PostgreSQL, SQLAlchemy, FastAPI, Pydantic, Streamlit을 서로 연결하는 과정에서 데이터 타입과 필드명을 일관되게 관리하는 것이 중요하다는 것을 확인하였다.

특히 데이터베이스 모델과 API Schema의 구조가 다르면 예상하지 못한 오류가 발생할 수 있었으며, CSV와 같이 외부에서 가져오는 데이터는 데이터베이스에 저장하기 전에 형식과 필수값을 검증해야 한다는 점을 알게 되었다.

또한 기능이 증가할수록 하나의 파일에 모든 코드를 작성하기보다 Router와 Schema 등 역할별로 코드를 분리하는 것이 유지보수와 협업에 효과적이라는 것을 경험하였다.
