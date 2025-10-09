package commandHandler

import (
	"dftp-server/entities"
	"fmt"
	"os"
)

func HandleLIST(session *entities.Session, cmd entities.Command) {	
	HandleNLST(session, cmd)
}


func ShowFileInfo(file os.FileInfo) string {
	var ans string = file.Name() + "\n" +
		file.Mode().String() + "\n" +
		fmt.Sprint(file.Size()) + "\n"
	return ans
}
