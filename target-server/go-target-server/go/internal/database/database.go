package database

import (
	"database/sql"
	"fmt"

	_ "github.com/mattn/go-sqlite3"
	"golang.org/x/crypto/bcrypt"

	// Local imports
	"target-server/internal/logger"
)

type Database struct {
	*sql.DB
}

func New(dbFile string) (*Database, error) {
	conn, err := sql.Open("sqlite3", dbFile)
	if err != nil {
		logger.Log(logger.ERROR, "Database connection failed", fmt.Sprintf("DB: '%s', Error: %v", dbFile, err))
		return nil, err
	}

	createTableSQL := `
    CREATE TABLE IF NOT EXISTS proxy_users (
        admin_id TEXT PRIMARY KEY,
        admin_secret_hash TEXT NOT NULL
    );`
	if _, err := conn.Exec(createTableSQL); err != nil {
		logger.Log(logger.ERROR, "Failed to create proxy_users table", err.Error())
		return nil, err
	}

	return &Database{conn}, nil
}

func (db *Database) AddUser(adminID, adminSecret string) (bool, error) {
	hashedSecret, err := bcrypt.GenerateFromPassword([]byte(adminSecret), bcrypt.DefaultCost)
	if err != nil {
		logger.Log(logger.ERROR, "Failed to hash admin secret", err.Error())
		return false, err
	}

	insertSQL := `INSERT OR REPLACE INTO proxy_users (admin_id, admin_secret_hash) VALUES (?, ?)`
	_, err = db.Exec(insertSQL, adminID, string(hashedSecret))
	if err != nil {
		logger.Log(logger.ERROR, "Failed to add admin user", fmt.Sprintf("Admin ID: '%s', Error: %v", adminID, err))
		return false, err
	}
	return true, nil
}

func (db *Database) VerifyUser(adminID, adminSecret string) (bool, error) {
	if adminID == "" || adminSecret == "" {
		return false, nil
	}

	var storedHash string
	querySQL := `SELECT admin_secret_hash FROM proxy_users WHERE admin_id = ?`
	err := db.QueryRow(querySQL, adminID).Scan(&storedHash)
	if err != nil {
		if err == sql.ErrNoRows {
			return false, nil
		}
		logger.Log(logger.ERROR, "Failed to query admin user", fmt.Sprintf("Admin ID: '%s', Error: %v", adminID, err))
		return false, err
	}

	err = bcrypt.CompareHashAndPassword([]byte(storedHash), []byte(adminSecret))
	return err == nil, nil
}
