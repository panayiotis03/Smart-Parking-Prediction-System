# 🅿️ Smart City Parking Predictor (Team DataVision)

Αυτό το README περιλαμβάνει την ολοκληρωμένη λύση Επιστήμης Δεδομένων για την πρόβλεψη διαθεσιμότητας θέσεων στάθμευσης σε πραγματικό χρόνο.

---

## 👥 Η Ομάδα μας
* Παναγιώτης Παναγιώτου
* Gabriel Vasile
---

## 📖 Τεκμηρίωση Συστήματος (Documentation)

###  Περιγραφή Συστήματος
Το σύστημα λειτουργεί ως μια έξυπνη γέφυρα μεταξύ των δεδομένων της πόλης και των οδηγών. 
**Real-time Data Pipeline:** Συλλέγει και συνθέτει δεδομένα (Data Fusion) κάθε **1 λεπτό** από 3 διαφορετικά APIs (TfL, TomTom, Visual Crossing).
* **Multi-threaded Ingestion:** Χρησιμοποιεί παράλληλη επεξεργασία για την ταυτόχρονη ανάκτηση κυκλοφοριακών δεδομένων από πολλαπλά σημεία.
* **Μοντελοποίηση:** Εφαρμόζει τεχνικές **Γραμμικής Παλινδρόμησης (Regression)** και ανάλυση τάσεων (Trend Analysis) για την πρόβλεψη πληρότητας σε ορίζοντα 5-60 λεπτών.

---

## 📦 Οδηγίες Εγκατάστασης (Local Run)

Για να τρέξετε το project τοπικά στον υπολογιστή σας, ακολουθήστε τα παρακάτω βήματα:

 **Κλωνοποίηση του Repository:**
   git clone [https://github.com/panayiotis03/Smart-Parking-Prediction-System.git](https://github.com/panayiotis03/Smart-Parking-Prediction-System.git)
   cd Smart-Parking-Prediction-System
   
**Εγκατάσταση Βιβλιοθηκών:**
Εγκαταστήστε όλες τις απαραίτητες εξαρτήσεις που βρίσκονται στο αρχείο requirements.txt:

pip install -r requirements.txt

**Εγκατάσταση Αρχείων python:**
Αφού κατεβάσετε και τα 2 αρχεία python,όπου το ένα ειναι το smarticity.py που είναι ο collector των δεδομένων και το δεύτερο είναι το uiSmartCity.py που είναι το UI της εφαρμογής.Επιπλέον οταν τα τρέξετε local στον υπολογιστή σας χρειάζεται να βρίσκονται και τα δύο στο ίδιο path δηλαδη στο ίδιο φάκελο.

**Εκτέλεση της Εφαρμογής:**

**Εκτέλεση του Data Collector**
Πριν ανοίξετε το Dashboard, πρέπει να ξεκινήσετε τη συλλογή δεδομένων για να ενημερωθεί η βάση SQL:
python smartcity.py

**Εκτέλεση της Dashboard:**
Σε ένα νέο τερματικό, τρέξτε την εφαρμογή UI:
python -m streamlit run uiSmartCity.py

**Εκτέλεση του Dashboard:**
Θα ανόιξει αυτόματα ο browser ή ανοίξτε τον browser σας στη διεύθυνση: http://localhost:8501

**Εκτέλεση Πίνακα Ελέγχου σε οποιαδήποτε Local συσκευή:**
Ανοίξτε τον browser σας στη διεύθυνση "Network URL" που εμφανίζεται στο Command Prompt (CMD)
