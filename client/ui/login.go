package ui

import (
	"dftp-client/modules"
	"fmt"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"
)

func StartApp() {
	a := app.New()
	w := a.NewWindow("D-FTP Client - Login")

	ipEntry := widget.NewEntry()
	ipEntry.SetPlaceHolder("127.0.0.1")

	portEntry := widget.NewEntry()
	portEntry.SetPlaceHolder("2121")

	userEntry := widget.NewEntry()
	userEntry.SetPlaceHolder("Usuario (opcional)")

	passEntry := widget.NewPasswordEntry()
	passEntry.SetPlaceHolder("Contraseña (opcional)")

	status := widget.NewLabel("")

	//consolePlaceholder := container.NewVBox() // ocupará el espacio hasta abrir la consola

	connectBtn := widget.NewButton("Conectar", func() {
		ip := ipEntry.Text
		port := portEntry.Text
		if ip == "" || port == "" {
			status.SetText("⚠️ IP y puerto son obligatorios")
			return
		}

		client := modules.NewClient(ip, port)
		status.SetText("Conectando...")
		if err := client.Connect(); err != nil {
			status.SetText(fmt.Sprintf("❌ Error al conectar: %v", err))
			return
		}

		status.SetText("✅ Conectado")

		// Intentar login opcional y obtener respuestas
		if userEntry.Text != "" || passEntry.Text != "" {
			respUser, respPass, err := client.Login(userEntry.Text, passEntry.Text)
			if err != nil {
				status.SetText(fmt.Sprintf("❌ Error login: %v", err))
				// decidir si cerrar o no; por ahora no cerramos el cliente
			} else {
				// abrir consola y mostrar respuestas
				// cerramos la ventana de login y abrimos la consola
				w.Hide()
				console := NewConsoleUI(client)
				console.Start()
				// mostrar las respuestas iniciales en la consola
				console.printNormal(strings.TrimRight(respUser, "\r\n"))
				console.printSuccess(strings.TrimRight(respPass, "\r\n"))
				return
			}
		}

		// Si no hay credenciales, abrir consola directamente
		w.Hide()
		console := NewConsoleUI(client)
		console.Start()
	})

	form := container.NewVBox(
		widget.NewLabelWithStyle("Cliente D-FTP", fyne.TextAlignCenter, fyne.TextStyle{Bold: true}),
		widget.NewLabel("IP del servidor:"),
		ipEntry,
		widget.NewLabel("Puerto:"),
		portEntry,
		widget.NewLabel("Usuario:"),
		userEntry,
		widget.NewLabel("Contraseña:"),
		passEntry,
		connectBtn,
		status,
	)

	w.SetContent(container.NewCenter(form))
	w.Resize(fyne.NewSize(420, 420))
	w.ShowAndRun()
}
