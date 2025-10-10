package modules

import "fmt"

func (c *Client) Login(user, pass string) (string, string, error) {
	// Enviar USER
	if err := c.SendCommand("USER " + user); err != nil {
		return "", "", err
	}
	responseUser, err := c.ReadResponse()
	if err != nil {
		return "", "", err
	}
	fmt.Println("Server:", responseUser)

	// Enviar PASS
	if err := c.SendCommand("PASS " + pass); err != nil {
		return "", "", err
	}
	responsePass, err := c.ReadResponse()
	if err != nil {
		return "", "", err
	}
	fmt.Println("Server:", responsePass)

	return responseUser, responsePass, nil
}
