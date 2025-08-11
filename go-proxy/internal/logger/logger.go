package logger

import (
	"fmt"
	"log"
	"time"
)

type Level int

const (
	INFO Level = iota
	WARN
	ERROR
	SUCCESS
)

func (l Level) String() string {
	switch l {
	case INFO:
		return "INFO"
	case WARN:
		return "WARN"
	case ERROR:
		return "ERROR"
	case SUCCESS:
		return "SUCCESS"
	default:
		return "UNKNOWN"
	}
}

func Init() {
	log.SetFlags(0)
}

func Log(level Level, message string, extras ...interface{}) {
	timestamp := time.Now().Format("2006-01-02 15:04:05.000")
	levelStr := fmt.Sprintf("%-7s", level)
	logMessage := fmt.Sprintf("[%s] %s :: %s", timestamp, levelStr, message)

	if len(extras) > 0 {
		logMessage += " :: " + fmt.Sprint(extras...)
	}

	log.Println(logMessage)
}
