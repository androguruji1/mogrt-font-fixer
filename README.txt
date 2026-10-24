MOGRT FONT FIXER  v2.0   (Mac + Windows)
========================================

KYA KARTA HAI
-------------
Premiere Pro me jo .mogrt templates install hain, unke fonts padhta hai.
Jo font system me nahi hai:
  1. use free sites se dhundh ke apne aap install karta hai
     (Google Fonts, Font Squirrel, DaFont, 1001 Fonts, Befonts)
  2. jo paid font kahin free nahi milta, uski jagah ek milta-julta free font
     usi naam se laga deta hai (isko "stand-in" kehte hain), taaki Premiere me
     "missing font" ka sign na aaye
Naya mogrt install karte hi ye sab apne aap hota hai. Kuch kholna nahi padta.


========================================
PEHLI BAAR: INSTALL
========================================

MAC
---
1. Zip pe double-click karo. "MogrtFontFixer" folder banega.
2. Terminal kholo (Cmd+Space dabao, "Terminal" likho, Enter).
3. Terminal me likho:   bash
   uske baad ek space do, phir folder ke andar ki "install.sh" file ko
   Terminal ki window me drag karke chhod do, aur Enter dabao.
4. Pehla scan 2-10 minute lega. Khatam hote hi browser me report khulegi.
5. Ab zip aur extract hua folder delete kar sakte ho. Tool apni jagah
   copy ho chuka hai:  Home > Applications > MogrtFontFixer

WINDOWS (10 / 11)
-----------------
1. Zip pe right-click > "Extract All". (Zip ke andar se seedha mat chalana.)
2. Extract hue folder me "install_windows.bat" pe double-click karo.
3. Neeli window aaye "Windows protected your PC" toh
   "More info" > "Run anyway" dabao.
4. Pehli baar tool apna chhota Python download karta hai (lagbhag 40 MB),
   phir pehla scan 2-10 minute lega. Kaali window band mat karna.
   Khatam hote hi browser me report khulegi.
5. Ab zip aur extract hua folder delete kar sakte ho. Tool apni jagah
   copy ho chuka hai:  %LOCALAPPDATA%\MogrtFontFixer
   (ye path File Explorer ke address bar me paste karke khul jata hai)


========================================
AAGE KE LIYE: ROZ KA KAAM
========================================

Kuch nahi karna. PC / Mac start hote hi tool background me khud chalu
ho jata hai aur mogrt folder pe nazar rakhta hai.

- Naya mogrt install kiya: 15-20 second me uske fonts check hote hain.
  Kuch install hua ya nahi mila toh notification aati hai aur report khulti hai.
- Din me ek baar tool khud dobara check karta hai aur apna kachra saaf karta hai.
- Font aane ke baad bhi Premiere me missing dikhe: project band karke dobara
  kholo, ya Premiere restart karo.

Khud se full scan chalana ho
  Mac:     Home > Applications > "Mogrt Font Scan" pe double-click
  Windows: Desktop ya Start menu me "Mogrt Font Scan" pe double-click

Koi ek file check karni ho (.mogrt, .prproj ya .aep)
  Us file ko "Mogrt Font Scan" ke icon pe drag karke chhod do.
  (.prproj ke andar ke fonts andaze se nikalte hain, kuch galat ho sakte hain.)

Report dekhni ho
  Tool ke folder me "report.html" kholo. Usme teen list hain:
  auto-install hue fonts, stand-in lage fonts, aur jo bilkul nahi mile
  (unke saamne seedhe search ke links).

Mogrt kisi aur folder me bhi rakhte ho toh wo folder jodne ke liye
  Mac (Terminal):
    python3 ~/Applications/MogrtFontFixer/mogrt_font_fixer.py add-folder "/poora/path"
  Windows (Command Prompt):
    "%LOCALAPPDATA%\MogrtFontFixer\python\python.exe" "%LOCALAPPDATA%\MogrtFontFixer\mogrt_font_fixer.py" add-folder "D:\poora\path"


========================================
STAND-IN FONTS (ZAROOR PADHO)
========================================

- Stand-in asli font nahi hai. Ye ek free font hai jo paid font ke naam se
  install hota hai. Look milta-julta hota hai, bilkul same nahi.
- Font menu me ye "(Stand-in)" likh ke dikhta hai, aur file ka naam
  "STANDIN__" se shuru hota hai.
- Client ko exact font chahiye toh asli font kharid ke install karo aur
  STANDIN__ wali file hata do, warna dono takrayenge.
    Mac fonts folder:      Home > Library > Fonts
    Windows fonts folder:  %LOCALAPPDATA%\Microsoft\Windows\Fonts
- Jis mogrt ke liye stand-in laga tha wo mogrt hata do, toh uska stand-in
  font bhi agle scan me apne aap hat jata hai.
- Stand-in bilkul nahi chahiye:
    Mac:      python3 ~/Applications/MogrtFontFixer/mogrt_font_fixer.py remove-standins
    Windows:  "%LOCALAPPDATA%\MogrtFontFixer\python\python.exe" "%LOCALAPPDATA%\MogrtFontFixer\mogrt_font_fixer.py" remove-standins
- Kisi font ka stand-in badalna ho (jaise Gilroy ki jagah Poppins): tool ke
  folder me config.json kholo aur "standin_map" me likho:
    "standin_map": {"Gilroy": "Poppins"}
  Naam Google Fonts wala hona chahiye.


========================================
MEMORY AUR STORAGE
========================================

Tool halka rehne ke liye bana hai:
- Background me sirf ek chhota process chalta hai (lagbhag 15-25 MB RAM),
  aur har 15 second me bas folder ki list dekhta hai.
- Scan ke baad memory turant chhod deta hai.
- Log file 1 MB se badi nahi hoti, purana hissa apne aap hat jata hai.
- Download ka cache har scan ke baad saaf, debug files 7 din baad saaf.
- Adhoori downloads aur temporary files apne aap hat jati hain.
- Ek time pe ek hi scan aur ek hi background process chalta hai.
Tool ka folder aam taur pe 1-3 MB rehta hai (Windows pe apna Python
alag se lagbhag 30 MB leta hai, wo ek hi baar aata hai).
Jo fonts install hote hain wo fonts folder me rehte hain, wo kachra nahi hain.

Abhi turant safai karni ho:
    Mac:      python3 ~/Applications/MogrtFontFixer/mogrt_font_fixer.py cleanup
    Windows:  "%LOCALAPPDATA%\MogrtFontFixer\python\python.exe" "%LOCALAPPDATA%\MogrtFontFixer\mogrt_font_fixer.py" cleanup


========================================
DHYAN RAKHO
========================================

- DaFont jaisi sites ke kai fonts sirf personal use ke liye free hain.
  Client / commercial kaam me font ka license khud check karo.
- Paid fonts ko pirated sites se download karna is tool me nahi hai.
  Unke liye stand-in lagta hai aur report me asli font ke links milte hain.
- Jo fonts Adobe Fonts me hain unhe Premiere khud activate kar leta hai.
- Tool ko internet chahiye. Internet na ho toh agle scan me dobara koshish hoti hai.


========================================
UPDATE AUR UNINSTALL
========================================

Naya version aaye toh
  Nayi zip kholo aur install wahi tareeke se dobara chala do.
  Purani settings aur report bani rehti hai.

Poora hatana ho
  Mac (Terminal):   bash ~/Applications/MogrtFontFixer/uninstall.sh
  Windows:          %LOCALAPPDATA%\MogrtFontFixer  folder me
                    "uninstall_windows.bat" pe double-click
  Isse auto-start, shortcut, stand-in fonts aur tool ka folder hat jata hai.
  Jo asli fonts install hue the wo rehte hain.


========================================
KUCH GADBAD HO TOH
========================================

Tool ke folder me "log.txt" hoti hai, usme sab likha hota hai ki kya hua.
  Mac:      Home > Applications > MogrtFontFixer > log.txt
  Windows:  %LOCALAPPDATA%\MogrtFontFixer\log.txt
Ye file bhej do, usse pata chal jata hai dikkat kahan hai.
