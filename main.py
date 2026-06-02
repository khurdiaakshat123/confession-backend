import hashlib
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict

import models
import schemas
from database import engine, get_db

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Anonymous Confession API",
    description="Backend service for Anonymous Confession rooms",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For simplicity in local dev / docker environments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_room_and_verify_password(room_name: str, db: Session, x_room_password: str = Header(...)):
    room_name = room_name.strip().lower()
    room = db.query(models.Room).filter(models.Room.name == room_name).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{room_name}' not found"
        )
    
    hashed_pwd = hash_password(x_room_password)
    if room.password_hash != hashed_pwd:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect room password"
        )
    return room

@app.post("/api/rooms", response_model=schemas.RoomStatusResponse, status_code=status.HTTP_201_CREATED)
def create_room(room_data: schemas.RoomCreate, db: Session = Depends(get_db)):
    normalized_name = room_data.name.strip().lower()
    # Check if room already exists
    existing_room = db.query(models.Room).filter(models.Room.name == normalized_name).first()
    if existing_room:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room '{room_data.name}' already exists"
        )

    # Validate participant list
    if len(room_data.participant_names) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A room must have at least 2 participants"
        )

    # Create new Room
    db_room = models.Room(
        name=normalized_name,
        password_hash=hash_password(room_data.password),
        status="collecting"
    )
    db.add(db_room)
    db.commit()
    db.refresh(db_room)

    # Add participants
    for name in room_data.participant_names:
        db_participant = models.Participant(
            room_name=db_room.name,
            name=name.strip(),
            has_confessed=False
        )
        db.add(db_participant)
    
    db.commit()
    db.refresh(db_room)
    return db_room

@app.post("/api/rooms/verify", response_model=schemas.RoomStatusResponse)
def verify_room(verify_data: schemas.RoomVerify, db: Session = Depends(get_db)):
    normalized_name = verify_data.name.strip().lower()
    room = db.query(models.Room).filter(models.Room.name == normalized_name).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{verify_data.name}' not found"
        )
    
    hashed_pwd = hash_password(verify_data.password)
    if room.password_hash != hashed_pwd:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect room password"
        )
    
    return room

@app.get("/api/rooms/{room_name}/status", response_model=schemas.RoomStatusResponse)
def get_room_status(room_name: str, db: Session = Depends(get_db)):
    # Publicly accessible to allow clients to check progress
    normalized_name = room_name.strip().lower()
    room = db.query(models.Room).filter(models.Room.name == normalized_name).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{room_name}' not found"
        )
    return room

@app.post("/api/rooms/{room_name}/confessions", status_code=status.HTTP_200_OK)
def submit_confessions(
    room_name: str,
    payload: schemas.ConfessionsSubmitRequest,
    db: Session = Depends(get_db),
    x_room_password: str = Header(...)
):
    # Verify room and password
    room = get_room_and_verify_password(room_name, db, x_room_password)
    room_name = room.name

    if room.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room is already closed. Submissions are no longer accepted."
        )

    # Validate submitting participant
    submitting_participant = db.query(models.Participant).filter(
        models.Participant.id == payload.from_participant_id,
        models.Participant.room_name == room_name
    ).first()

    if not submitting_participant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submitting participant not found in this room"
        )

    if submitting_participant.has_confessed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Participant '{submitting_participant.name}' has already submitted confessions"
        )

    # Store confessions
    for confession_input in payload.confessions:
        txt = confession_input.confession_text.strip()
        if not txt:
            continue  # Skip empty confessions

        # Verify target participant exists
        target = db.query(models.Participant).filter(
            models.Participant.id == confession_input.target_id,
            models.Participant.room_name == room_name
        ).first()

        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target participant ID {confession_input.target_id} not found in this room"
            )

        # Ensure a player cannot write a confession to themselves (unless intended, but logic says others)
        if target.id == submitting_participant.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot write a confession about yourself"
            )

        db_confession = models.Confession(
            room_name=room_name,
            target_participant_id=target.id,
            confession_text=txt
        )
        db.add(db_confession)

    # Mark participant as confessed
    submitting_participant.has_confessed = True
    db.commit()

    # Check if all participants have confessed
    all_participants = db.query(models.Participant).filter(models.Participant.room_name == room_name).all()
    if all(p.has_confessed for p in all_participants):
        room.status = "completed"
        db.commit()

    return {"detail": "Confessions submitted successfully", "room_status": room.status}

@app.get("/api/rooms/{room_name}/results", response_model=schemas.RoomResultsResponse)
def get_room_results(room_name: str, db: Session = Depends(get_db), x_room_password: str = Header(...)):
    # Verify room and password
    room = get_room_and_verify_password(room_name, db, x_room_password)

    # Retrieve all participants and their confessions
    participants = db.query(models.Participant).filter(models.Participant.room_name == room_name).all()
    
    results = {}
    for p in participants:
        # Query confessions for this participant
        confessions = db.query(models.Confession).filter(
            models.Confession.room_name == room_name,
            models.Confession.target_participant_id == p.id
        ).all()
        
        results[p.name] = [c.confession_text for c in confessions]

    return {
        "room_name": room.name,
        "status": room.status,
        "results": results
    }

@app.post("/api/rooms/{room_name}/participants", response_model=schemas.RoomStatusResponse)
def add_participant(
    room_name: str,
    payload: schemas.ParticipantCreate,
    db: Session = Depends(get_db),
    x_room_password: str = Header(...)
):
    room = get_room_and_verify_password(room_name, db, x_room_password)
    room_name = room.name

    existing = db.query(models.Participant).filter(
        models.Participant.room_name == room_name,
        models.Participant.name == payload.name.strip()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Participant '{payload.name}' already exists in this room"
        )

    new_p = models.Participant(
        room_name=room_name,
        name=payload.name.strip(),
        has_confessed=False
    )
    db.add(new_p)
    room.status = "collecting"
    
    db.commit()
    db.refresh(room)
    return room

@app.delete("/api/rooms/{room_name}/participants/{participant_id}", response_model=schemas.RoomStatusResponse)
def delete_participant(
    room_name: str,
    participant_id: int,
    db: Session = Depends(get_db),
    x_room_password: str = Header(...)
):
    room = get_room_and_verify_password(room_name, db, x_room_password)
    room_name = room.name

    p = db.query(models.Participant).filter(
        models.Participant.room_name == room_name,
        models.Participant.id == participant_id
    ).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found in this room"
        )

    db.delete(p)
    db.commit()

    all_participants = db.query(models.Participant).filter(models.Participant.room_name == room_name).all()
    if not all_participants:
        room.status = "collecting"
    elif all(x.has_confessed for x in all_participants):
        room.status = "completed"
    else:
        room.status = "collecting"
        
    db.commit()
    db.refresh(room)
    return room

