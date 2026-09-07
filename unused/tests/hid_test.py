import hid


def main():
    print('=== HID Device List ===\n')
    
    for d in hid.enumerate():
        vid = d['vendor_id']
        pid = d['product_id']
        product = d.get('product_string', '')
        manufacturer = d.get('manufacturer_string', '')
        
        # ゲームパッド候補
        if any(k in product.lower() for k in ['xbox', 'controller', 'gamepad', 'pad']):
            print(f'VID: 0x{vid:04x}  PID: 0x{pid:04x}')
            print(f'  Product:      {product}')
            print(f'  Manufacturer: {manufacturer}')
            print(f'  Usage:        {d.get("usage", "?")}')
            print(f'  Usage Page:   {d.get("usage_page", "?")}')
            print()
    
    print('=== All Microsoft/Xbox devices ===\n')
    for d in hid.enumerate():
        vid = d['vendor_id']
        if vid == 0x045e:  # Microsoft
            print(f'VID: 0x{vid:04x}  PID: 0x{d["product_id"]:04x}')
            print(f'  Product: {d.get("product_string", "")}')
            print(f'  Path:    {d["path"]}')
            print()


if __name__ == '__main__':
    main()