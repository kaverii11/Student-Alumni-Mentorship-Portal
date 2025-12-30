# Student-Alumni Mentorship Portal 🎓

A database-driven web application designed to bridge the gap between students and alumni by streamlining mentorship assignments, session scheduling, and feedback.

## 🚀 Features
* **Role-Based Access:** Distinct portals for Students, Alumni, and Administrators.
* **Smart Search:** Mentors can be filtered by industry and rating using **Stored Procedures**.
* **Real-Time Analytics:** **Stored Functions** calculate mentor reputation scores dynamically based on student feedback.
* **Session Tracking:** Complete lifecycle management from request to session completion logs.

## 🛠️ Tech Stack
* **Frontend:** Streamlit (Python)
* **Backend:** MySQL
* **Database Concepts:** Triggers, Stored Procedures, Functions, Normalization (3NF), ACID Properties.

## 📂 Database Structure
The system is built on a relational schema including:
* `Alumni` & `Student` (Master Tables)
* `Mentorship_Request` & `Mentorship_Session` (Transaction Tables)
* `Feedback` (Analytics)

## ⚙️ How to Run
1.  **Clone the repo:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/Student-Alumni-Mentorship-Portal.git](https://github.com/YOUR_USERNAME/Student-Alumni-Mentorship-Portal.git)
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up the Database:**
    * Import the `schema.sql` file into your MySQL Workbench.
    * Update your database credentials in `app.py` or `.env`.
    
4.  **Run the App:**
    ```bash
    streamlit run app2.py
    ```

## 👥 Contributors
* **Kaveri Sharma** (PES1UG23CS293)
* **Janya Mahesh** (PES1UG23CS259)
