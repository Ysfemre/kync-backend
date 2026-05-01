import os
import shutil
import uuid
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import mysql.connector

# API Başlatma
app = FastAPI(title="KYNC Emlak API")

# CORS Ayarları: Vercel gibi dış sunuculardan (farklı domainlerden) gelen isteklere izin vermek için allow_origins=["*"] yapıldı.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyalar (Fotoğraflar) için dizin oluşturma ve dışa açma
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Aiven Bulut Veritabanı Bağlantısı
def get_db_connection():
    return mysql.connector.connect(
        host="kync-kyncgayrimenkul.h.aivencloud.com",
        port=18441,
        user="avnadmin",
        password="AVNS_VYRgmmIHmgiOPnWhj6S", 
        database="defaultdb"
    )

# İlan Veri Modeli
class IlanBase(BaseModel):
    ilan_turu: Optional[str] = "konut"
    baslik: str
    aciklama: Optional[str] = ""
    fiyat: float
    m2: int
    il: Optional[str] = "Burdur"
    ilce: Optional[str] = "Merkez"
    enlem: Optional[float] = None
    boylam: Optional[float] = None
    tapu_durumu: Optional[str] = ""
    imar_durumu: Optional[str] = ""
    ilan_durumu: Optional[str] = "satilik"
    oda_sayisi: Optional[str] = ""
    banyo_sayisi: Optional[str] = ""
    kat_sayisi: Optional[str] = ""
    bulundugu_kat: Optional[str] = ""
    bina_yasi: Optional[str] = ""
    isinma_tipi: Optional[str] = ""
    esya_durumu: Optional[str] = ""
    cephe: Optional[str] = ""
    asansor: Optional[str] = "0"

# 1. Tüm ilanları listeleme
@app.get("/ilanlar")
def get_ilanlar():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # Alt sorgu ile her ilanın sadece ilk fotoğrafını kapak resmi olarak alıyoruz
    sql = """
        SELECT i.*, 
               (SELECT f.fotograf_url FROM ilan_fotograflari f WHERE f.ilan_id = i.id LIMIT 1) as kapak_resmi 
        FROM ilanlar i
    """
    cursor.execute(sql)
    ilanlar = cursor.fetchall()
    db.close()
    return {"ilanlar": ilanlar}

# 2. Tekil ilan detayı ve galeri verisi
@app.get("/ilanlar/{ilan_id}")
def get_ilan_detay(ilan_id: int):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    # İlan temel bilgileri
    sql_ilan = """
        SELECT i.*, 
               (SELECT f.fotograf_url FROM ilan_fotograflari f WHERE f.ilan_id = i.id LIMIT 1) as kapak_resmi 
        FROM ilanlar i WHERE i.id = %s
    """
    cursor.execute(sql_ilan, (ilan_id,))
    ilan = cursor.fetchone()
    
    if not ilan:
        db.close()
        return {"ilan_detayi": None}
        
    # İlana ait tüm galeri fotoğrafları
    sql_fotolar = "SELECT fotograf_url FROM ilan_fotograflari WHERE ilan_id = %s"
    cursor.execute(sql_fotolar, (ilan_id,))
    fotograflar = cursor.fetchall()
    ilan["galeri"] = [foto["fotograf_url"] for foto in fotograflar]
    
    db.close()
    return {"ilan_detayi": ilan}

# 3. Yeni ilan ekleme
@app.post("/ilan-ekle")
def add_ilan(ilan: IlanBase):
    db = get_db_connection()
    cursor = db.cursor()
    sql = """
        INSERT INTO ilanlar 
        (ilan_turu, baslik, aciklama, fiyat, m2, il, ilce, enlem, boylam, tapu_durumu, imar_durumu, 
         ilan_durumu, oda_sayisi, banyo_sayisi, kat_sayisi, bulundugu_kat, bina_yasi, 
         isinma_tipi, esya_durumu, cephe, asansor) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    val = (
        ilan.ilan_turu, ilan.baslik, ilan.aciklama, ilan.fiyat, ilan.m2, ilan.il, ilan.ilce, ilan.enlem, ilan.boylam, 
        ilan.tapu_durumu, ilan.imar_durumu, ilan.ilan_durumu, ilan.oda_sayisi, ilan.banyo_sayisi, 
        ilan.kat_sayisi, ilan.bulundugu_kat, ilan.bina_yasi, ilan.isinma_tipi, ilan.esya_durumu, 
        ilan.cephe, ilan.asansor
    )
    cursor.execute(sql, val)
    yeni_ilan_id = cursor.lastrowid
    db.commit()
    db.close()
    return {"mesaj": "İlan başarıyla eklendi!", "ilan_id": yeni_ilan_id}

# 4. İlan silme (Cascade özelliği ile bağlı fotoğraflar da veritabanından silinir)
@app.delete("/ilanlar/{ilan_id}")
def delete_ilan(ilan_id: int):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM ilanlar WHERE id = %s", (ilan_id,))
    db.commit()
    db.close()
    return {"mesaj": "İlan başarıyla silindi!"}

# 5. İlan güncelleme
@app.put("/ilanlar/{ilan_id}")
def update_ilan(ilan_id: int, ilan: IlanBase):
    db = get_db_connection()
    cursor = db.cursor()
    sql = """
        UPDATE ilanlar SET 
        ilan_turu=%s, baslik=%s, aciklama=%s, fiyat=%s, m2=%s, il=%s, ilce=%s, enlem=%s, boylam=%s, 
        tapu_durumu=%s, imar_durumu=%s, ilan_durumu=%s, oda_sayisi=%s, banyo_sayisi=%s, 
        kat_sayisi=%s, bulundugu_kat=%s, bina_yasi=%s, isinma_tipi=%s, esya_durumu=%s, 
        cephe=%s, asansor=%s 
        WHERE id=%s
    """
    val = (
        ilan.ilan_turu, ilan.baslik, ilan.aciklama, ilan.fiyat, ilan.m2, ilan.il, ilan.ilce, ilan.enlem, ilan.boylam, 
        ilan.tapu_durumu, ilan.imar_durumu, ilan.ilan_durumu, ilan.oda_sayisi, ilan.banyo_sayisi, 
        ilan.kat_sayisi, ilan.bulundugu_kat, ilan.bina_yasi, ilan.isinma_tipi, ilan.esya_durumu, 
        ilan.cephe, ilan.asansor, ilan_id
    )
    cursor.execute(sql, val)
    db.commit()
    db.close()
    return {"mesaj": "İlan başarıyla güncellendi!"}

# 6. Çoklu fotoğraf yükleme işlemi
@app.post("/ilanlar/{ilan_id}/fotograf")
async def fotograf_yukle(ilan_id: int, dosyalar: List[UploadFile] = File(...)):
    if len(dosyalar) < 1:
        raise HTTPException(status_code=400, detail="Lütfen en az 1 fotoğraf seçin.")
    if len(dosyalar) > 10:
        raise HTTPException(status_code=400, detail="En fazla 10 fotoğraf yükleyebilirsiniz.")

    baglanti = get_db_connection()
    cursor = baglanti.cursor()
    
    yuklenen_urller = []

    for dosya in dosyalar:
        # Türkçe karakter ve boşluk sorunlarını önlemek için UUID ile benzersiz isim oluşturma
        uzanti = dosya.filename.split(".")[-1]
        yeni_isim = f"{uuid.uuid4().hex}.{uzanti}"
        
        dosya_yolu = f"uploads/{ilan_id}_{yeni_isim}"
        with open(dosya_yolu, "wb") as buffer:
            shutil.copyfileobj(dosya.file, buffer)
        
        # Dosya yolunu veritabanına kaydetme
        resim_url = f"/{dosya_yolu}" 
        sql = "INSERT INTO ilan_fotograflari (ilan_id, fotograf_url) VALUES (%s, %s)"
        cursor.execute(sql, (ilan_id, resim_url))
        yuklenen_urller.append(resim_url)
    
    baglanti.commit()
    baglanti.close()
    
    return {"mesaj": f"{len(dosyalar)} fotoğraf eklendi!", "urller": yuklenen_urller}