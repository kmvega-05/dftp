package modules

import (
	"fmt"
	"net"
	"regexp"
	"strconv"
)

func (c *Client) EnterPassiveMode() error {
	if err := c.SendCommand("PASV"); err != nil {
		return err
	}
	response, err := c.ReadResponse()
	if err != nil {
		return err
	}
	fmt.Println("Server: ", response)
	dataConn, err := c.ParsePASVResponse(response)
	if err != nil {
		return err
	}
	c.DataConn = dataConn
	return nil
}

func (c *Client) ParsePASVResponse(response string) (net.Conn, error) {
	// Buscar patron (h1,h2,h3,h4,p1,p2)
	re := regexp.MustCompile(`\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)`)
	matches := re.FindStringSubmatch(response)
	if len(matches) != 7 {
		return nil, fmt.Errorf("invalid PASV response format")
	}

	// Construir IP y puerto
	ip := fmt.Sprintf("%s.%s.%s.%s", matches[1], matches[2], matches[3], matches[4])
	p1, _ := strconv.Atoi(matches[5])
	p2, _ := strconv.Atoi(matches[6])
	port := p1*256 + p2

	dataAddr := fmt.Sprintf("%s:%d", ip, port)
	conn, err := net.Dial("tcp", dataAddr)
	if err != nil {
		return nil, err
	}

	return conn, nil
}

func (c *Client) List() (string, error) {
	if err := c.EnterPassiveMode(); err != nil {
		return "", err
	}
	defer c.DataConn.Close()
	if err := c.SendCommand("LIST"); err != nil {
		return "", err
	}
	response, err := c.ReadResponse()
	if err != nil {
		return "", err
	}
	return response, nil
}
