package main

import (
	"flag"
	"fmt"

	// Local imports
	"target-server/internal/database"
	"target-server/internal/logger"
)

func main() {
	logger.Init()

	id := flag.String("id", "", "The Admin 'id' for the proxy.")
	secret := flag.String("secret", "", "The Admin 'secret' for the proxy.")
	flag.Parse()

	if *id == "" || *secret == "" {
		logger.Log(logger.ERROR, "Admin ID and secret cannot be empty.")
		return
	}

	db, err := database.New("users.db")
	if err != nil {
		return
	}
	defer db.Close()

	if ok, _ := db.AddUser(*id, *secret); ok {
		logger.Log(logger.SUCCESS, "Added admin user", fmt.Sprintf("Admin ID: '%s'", *id))
	} else {
		logger.Log(logger.ERROR, "Failed to add user", fmt.Sprintf("Admin ID: '%s'", *id))
	}
}
