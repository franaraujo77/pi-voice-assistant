# Setup LED service
setup_led_service() {
    log_info "Setting up LED service..."
    
    # Create virtual environment for LED service
    cd "$INSTALL_DIR/wyoming-satellite/examples"
    python3 -m venv --system-site-packages .venv
    source .venv/bin/activate
    pip3 install --upgrade pip wheel setuptools
    pip3 install 'wyoming==1.5.2'
    deactivate
    
    # Copy LED service script
    cp "$SCRIPT_DIR/config/2mic_service.py" "$INSTALL_DIR/wyoming-satellite/examples/"
    chmod +x "$INSTALL_DIR/wyoming-satellite/examples/2mic_service.py"
    
    # Install LED service
    cp "$SCRIPT_DIR/config/2mic_leds.service" /etc/systemd/system/
    systemctl enable 2mic_leds.service
    systemctl start 2mic_leds.service
    
    check_success "LED service setup"
}