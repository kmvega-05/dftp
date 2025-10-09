package modules

import "fmt"

func (c *Client) Login(user, pass string) error {
	// Formato correcto: "USER <username>"
	respUser, err := c.SendCommand("USER " + user)
	if err != nil {
		return err
	}
	fmt.Println("Server: " + respUser)
	respPass, err := c.SendCommand("PASS " + pass)
	if err != nil {
		return err
	}
	fmt.Println("Server: " + respPass)
	return nil
}
