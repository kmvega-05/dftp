package modules

func (c *Client) Login(user, pass string) (string, string, error) {
	respUser, err := c.SendCommand("USER " + user)
	if err != nil {
		return respUser, "", err
	}
	respPass, err := c.SendCommand("PASS " + pass)
	if err != nil {
		return respUser, respPass, err
	}
	return respUser, respPass, nil
}
