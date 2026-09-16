# ❤️ sayangin

## Tautan Penting
- PWS Deployment: TBA
- Figma Design: TBA

## Deskripsi dan Overview
Sayangin merupakan platform belanja online untuk barang *preloved* yang masih layak pakai. Hal yang membedakan kami dari produk serupa lainnya adalah setiap pengguna memiliki lemari digital untuk mendata barang-barang miliknya. Pengguna yang sudah lama tidak menggunakan suatu barang akan diberi pengingat dari sistem, dan akan diberikan opsi untuk menjual, mendonasikan, atau menyimpannya.

Kami juga memiliki fitur 'tunda beli', yaitu kemampuan menunda keinginan impulsif membeli barang baru yang sementara akan dimasukkan ke daftar tunggu. Sistem lalu akan mencarikan padanan versi *preloved*-nya terlebih dahulu.

Selain itu, fitur donasi tidak hanya sekadar memberikan barang yang sudah tidak terpakai ke lembaga yang membutuhkan, seperti panti sosial dan lembaga pendidikan. Melalui sistem kami, lembaga tersebut dapat memberikan daftar kebutuhan mereka secara spesifik sehingga pengguna dapat mencocokannya dengan barang yang ada di lemarinya, sehingga skema donasi tepat sasaran dan tidak ada barang yang terbuang.

Untuk meningkatkan inisiatif dan motivasi pengguna untuk membuat dampak yang bermakna, kami mengimplementasikan sistem gamifikasi dengan tantangan rutin, jejak progres yang bisa dibagikan ke teman-teman, *awards*/*achievements*, serta ringkasan dampak pribadi sejauh ini.

## Daftar Modul dan Pembagian
| Modul | Deskripsi | Penanggung Jawab
|:---|:---|:---:|
| **Autentikasi dan Profil Pengguna** | Berfungsi sebagai gerbang utama aplikasi yang mengelola akses masuk dan identitas secara aman. Modul membedakan hak akses akun personal dan akun lembaga, serta menyediakan akses untuk mengelola data diri, alamat pengiriman, dan preferensi akun mereka | Ghazi |
| **Marketplace dan Transaksi** | Pusat perputaran ekonomi sirkular dari website `sayangin`. Mencakup etalase katalog dengan sistem pencarian dan filter, manajemen keranjang belanja, alur penyelesaian transaksi (checkout), dan pencatatan riwayat pembelian | Ira |
| **Lemari Digital** |  Memungkinkan pengguna untuk mendata dan mengelola barang-barang pribadi mereka secara virtual. Sistem akan melacak kapan terakhir kali barang dipakai, memberikan notifikasi pengingat untuk barang yang sudah lama menganggur, dan menyediakan opsi untuk menjual, mendonasikan, atau menyimpannya kembali. | Daffa |
| **Donasi Tepat Sasaran** | Menjembatani niat baik pengguna dengan kebutuhan nyata di lapangan guna mencegah penumpukan barang donasi yang tidak berguna. Lembaga mitra bisa membuat dan mempublikasikan daftar kebutuhan barang yang spesifik, dan sistem akan mencocokkannya dengan barang-barang yang tidak terpakai dalam Lemari Digital pengguna. | Zaki |
| **Dampak dan Sosial (Gamifikasi)** | Memotivasi, memvalidasi, dan merayakan kontribusi pengguna terhadap gaya hidup berkelanjutan. Pengguna diberikan dasbor pribadi yang memvisualisasikan dampak positif mereka (seperti jumlah pembelian yang dicegah atau uang yang dihemat), serta dilengkapi dengan sistem papan peringkat (*leaderboard*), tantangan hijau bulanan, dan lencana pencapaian (*awards*). | Rena |
| **Tunda Beli (tentatif)** | Alat *eco-mindfulness* untuk meredam kebiasaan belanja impulsif. Pengguna bisa memasukkan barang baru yang ingin dibeli ke dalam wishlist dengan masa tunggu. Selama masa tunggu masih berjalan, sistem akan mencarikan dan menawarkan alternatif barang *preloved* serupa yang tersedia di dalam platform. | TBD |

## Application Programming Interface (API)

1. **DummyJSON** atau **FakeStoreAPI** sebagai penyedia data *dummy* berupa katalog produk e-commerce dengan atribut seperti nama barang, foto, harga, deskripsi, dan sebagainya.
2. **RajaOngkirAPI** sebagai penyedia data perhitungan tarif ongkos kirim dari berbagai ekspedisi di Indonesia.
3. **mockapi.io** untuk membuat API backend eksternal guna menampung data-data spesifik dari website `sayangin`, seperti `Lemari Digital` dan `Daftar Kebutuhan` barang dari panti sosial/lembaga kependidikan.

## Peran Pengguna Aplikasi
### User (Pengguna Personal)
Entitas penggerak utama dalam ekosistem **sayangin**. Setiap akun difasilitasi dengan Lemari Digital untuk mendata kepemilikan barang pribadi. Akun ini bersifat fleksibel, sehingga User dapat bertindak sebagai pembeli (*buyer*) sekaligus menjadi penjual (*seller*) yang bisa memindahkan barang dalam lemari ke katalog etalase tanpa harus membuat akun *seller* yang *dedicated*. Selain transaksi jual-beli, User juga berperan sebagai donatur yang bisa menyalurkan barang tidak terpakai mereka secara tepat sasaran berdasarkan kebutuhan lembaga.
### Lembaga Mitra / Institusi
Tipe akun khusus yang diperuntukkan bagi entitas penerima manfaat, seperti panti asuhan, panti jompo, sekolah, ataupun komunitas sosial. Akun ini tidak memiliki fitur Lemari Digital ataupun akses transaksi jual-beli. Akses Lembaga Mitra berpusat ke dasbor donasi dan mereka berwenang untuk memublikasikan daftar permintaan barang secara spesifik. Hal ini memastikan setiap donasi yang masuk dari User tepat sasaran dan berguna sesuai dengan kebutuhan lembaga. Lembaga Mitra juga bertanggung jawab untuk melakukan pembaruan status ketika barang donasi telah diterima secara fisik.

## Anggota Kelompok 6 - PBP D
- 2506551775	IRA ARIANTI ALAWIAH
- 2506584451	DAFFA AKMAL MAHADAYA PASARIBU
- 2506621945	RANIA YASIN
- 2506599541	MUHAMMAD ZAKI RADIPRADANA
- 2506537751	MUHAMMAD GHAZI ALFISYAHRI LATIEF