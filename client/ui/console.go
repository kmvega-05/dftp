package ui

import (
	"fmt"
	"image/color"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"

	"dftp-client/modules"
)

type ConsoleUI struct {
	client *modules.Client
	output *fyne.Container
	scroll *container.Scroll
	input  *widget.Entry
	win    fyne.Window
}

func NewConsoleUI(client *modules.Client) *ConsoleUI {
	out := container.NewVBox()
	scroll := container.NewVScroll(out)
	scroll.SetMinSize(fyne.NewSize(600, 300))

	input := widget.NewEntry()
	input.SetPlaceHolder("Escribe un comando FTP (ej: LIST, PWD, RETR file.txt)...")

	return &ConsoleUI{
		client: client,
		output: out,
		scroll: scroll,
		input:  input,
	}
}

// Start abre la ventana de la consola (usa fyne.CurrentApp)
func (c *ConsoleUI) Start() {
	c.win = fyne.CurrentApp().NewWindow("FTP Console")
	c.printNormal("Conectado al servidor FTP. Escribe comandos abajo. (quit para salir)")

	c.input.OnSubmitted = func(cmd string) {
		c.handleCommand(cmd)
	}

	content := container.NewBorder(nil, c.input, nil, nil, c.scroll)
	c.win.SetContent(content)
	c.win.Resize(fyne.NewSize(700, 500))
	c.win.Show()
}

func (c *ConsoleUI) handleCommand(cmd string) {
	cmd = strings.TrimSpace(cmd)
	if cmd == "" {
		return
	}

	// Comando local
	if strings.ToLower(cmd) == "quit" {
		c.printNormal("> quit")
		c.printNormal("Cerrando conexión...")
		_ = c.client.Close()
		// cerrar la app
		c.win.Close()
		fyne.CurrentApp().Quit()
		return
	}

	// Enviar al servidor y mostrar respuesta
	c.printNormal("> " + cmd)
	resp, err := c.client.SendCommand(cmd)
	if err != nil {
		c.printError(fmt.Sprintf("Error enviando comando: %v", err))
		return
	}
	if resp[0] == '5' || resp[0] == '4' {
		c.printError(fmt.Sprintf("%s", strings.TrimRight(resp, "\r\n")))
		return
	}
	c.printSuccess(strings.TrimRight(resp, "\r\n"))
}

// Métodos para imprimir en color
func (c *ConsoleUI) printNormal(msg string) {
	text := canvas.NewText(msg, color.NRGBA{R: 200, G: 200, B: 200, A: 255})
	text.TextSize = 14
	c.output.Add(text)
	c.scroll.ScrollToBottom()
}

func (c *ConsoleUI) printSuccess(msg string) {
	text := canvas.NewText(msg, color.NRGBA{R: 0, G: 200, B: 100, A: 255})
	text.TextSize = 14
	c.output.Add(text)
	c.scroll.ScrollToBottom()
}

func (c *ConsoleUI) printError(msg string) {
	text := canvas.NewText(msg, color.NRGBA{R: 220, G: 60, B: 60, A: 255})
	text.TextSize = 14
	c.output.Add(text)
	c.scroll.ScrollToBottom()
}
