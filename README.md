# 🅿️ Smart City Parking Predictor (Team DataVision)

Αυτό το README περιλαμβάνει την ολοκληρωμένη λύση Επιστήμης Δεδομένων για την πρόβλεψη διαθεσιμότητας θέσεων στάθμευσης σε πραγματικό χρόνο.

---

## 👥 Η Ομάδα μας
* Παναγιώτης Παναγιώτου
* Gabriel
---

## 📖 Τεκμηρίωση Συστήματος (Documentation)

### 1. Περιγραφή Συστήματος
Το σύστημα λειτουργεί ως μια έξυπνη γέφυρα μεταξύ των δεδομένων της πόλης και των οδηγών. 
* **Data Pipeline:** Συλλέγει δεδομένα κάθε 15 λεπτά από APIs και τα αποθηκεύει σε βάση SQL.
* **Μοντελοποίηση:** Χρησιμοποιεί αλγορίθμους παλινδρόμησης (Regression) για να προβλέψει τη μελλοντική πληρότητα.
* **Interface:** Παρέχει ένα διαδραστικό Dashboard με χάρτη.

---

## 📦 Οδηγίες Εγκατάστασης (Local Run)

Για να τρέξετε το project τοπικά στον υπολογιστή σας, ακολουθήστε τα παρακάτω βήματα:

 **Κλωνοποίηση του Repository:**
   git clone [https://github.com/panayiotis03/Smart-Parking-Prediction-System.git](https://github.com/panayiotis03/Smart-Parking-Prediction-System.git)
   cd Smart-Parking-Prediction-System
   
**Εγκατάσταση Βιβλιοθηκών:**
Εγκαταστήστε όλες τις απαραίτητες εξαρτήσεις που βρίσκονται στο αρχείο requirements.txt:

pip install -r requirements.txt

**Εκτέλεση της Εφαρμογής:**
**Τρέξτε το Dashboard μέσω του Streamlit:**
streamlit run app.py

**Πρόσβαση:**
Ανοίξτε τον browser σας στη διεύθυνση: http://localhost:8501
