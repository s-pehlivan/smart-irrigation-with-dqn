# Akıllı Sulama Report

## Ortam (Environment)

25 tane bitkinin 25 hücre içerisine yerleştirilmesiyle oluşturulan 5x5 bir tarla içinde, sulama robotu, her bir hücredeki bitki için ideal sulama miktarını bulmak zorundadır. Ajanın tarla içerisinde dolaşarak her bir hücre için sulama/sulamama kararı vererek o hücre için ideal nem miktarını koruması beklenir. Aynı zamanda bütün tarlanın hücrelerinden kaç tanesinin ideal nemden uzak olduğunu da bilir.

## Durum (State)

Sistemdeki bir state, sulama robotunun satır ve sütun konumları, robotun bulunduğu hücrenin o anki nem seviyesi, ve sistem genelindeki toplam nem seviyesi kötü olan hücre sayısına göre hesaplanan global panik seviyesinden oluşmaktadır.

Robotun bütün hücrelerdeki anlık nem seviyesini bilmesi, state değerinde üssel bir büyümeye sebep olacağından dolayı, robotun görebileceği tek hücrenin o an içinde bulunduğu hücre olması kısıtı getirilerek sistemdeki muhtemel state sayısı ciddi ölçüde azaltılmıştır. 

Eğer robotun bütün hücrelerdeki nem değerlerini bilmesine izin verilmiş olsaydı her bir hücredeki nem oranları hesabı üssel bir şekilde büyüyeceğinden dolayı hesaplanması gereken state değeri çok büyük bir rakama çıkacaktı. Dolayısıyla robotun görüşü kısıtlanarak sadece içinde bulunduğu hücrenin durumunu bilmesi ve diğer hücrelere karşı tamamen kör davranması sağlanmıştır.

State Değerleri:

Robot satır konumu, robot sütun konumu, toprak nem dereceleri, global panik seviyesi ⇒ 5x5x3x3


1. Robot Row (0-4)
2. Robot Col (0-4)
3. Current Soil Moisture (Buckets: Dry, Ideal, Wet)
4. Panic Level (0-3)

## State Değişkenleri

**Buckets:**

Tarla ortamı içerisindeki her hücrenin nem değeri float tipinde oluşturulmaktadır. Fakat bu değerler continuous olduğundan dolayı Q tablosu için discrete hale getirip her bir değeri eklemek mümkün olmadığından BUCKET mantığı bu continuous veriyi discrete veriye çevirerek Q tablosuna ekler.

Her bir BUCKET değeri hücrenin nem değerinin hangi yüzde aralığına girdiğini gösteren bir etiketi ifade etmektedir.

**Global Panik Seviyesi:**

Tarla ortamında kaç hücrenin ideal durumdan uzak olduğunu gösteren değerlerdir. Üç farklı değer alabilen panik seviyesi için; PANIC_CALM 0-3 aralığını, PANIC_WORRIED 4-10 aralığını ve PANIC_CRITICAL ise 10'dan fazla hücrenin kötü olduğunu gösterir.

## Robotun Hareketleri (Actions)

- MOVE_SOUTH: Robotun aşağı yönde hareketi
- MOVE_NORTH: Robotun yukarı yönde hareketi
- MOVE_EAST: Robotun sağa hareketi
- MOVE_WEST: Robotun sola hareketi
- WATER_HIGH: Hücrenin nem oranını +35 artırmak
- WATER_LOW: Hücrenin nem oranını +25 artırmak

## Action Mask:

Robot başarılı bir şekilde hücreyi ideal nem oranına getirdikten sonra ideal hücreler içinde gidip gelmesini önlemek ve daha kötü hücreleri keşfetmesini sağlamak için yapabileceği hareketler, action mask ile kısıtlanmış ve robotun döngüye girme riski azaltılmıştır. 

Aynı zamanda dört iterasyon boyunca iki hücre arasında gelip gidiyorsa yeni bir hücreye gitmeye zorlanacak şekilde bir maske de action_mask içinde bulunmaktadır. 

## Bölüm Tamamlanması kısıtları (Done Condition)

Bir bölümün (episode) ne zaman sonlanacağını belirlemek için üç farklı koşul kullanılmıştır. Bunlar; başarı, başarısızlık ve de maksimum adım olarak belirlenmiştir.

**Başarı:**

Bütün hücreler yeşil olursa ajan başarılı bir şekilde görevi gerçekleştirdiğinden bölüm sonlandırılır. (Positive Reward) Bu seviyeye ulaşmak için bütün hücrelerdeki nem seviyesinin %40-%70 aralığında olması beklenir.

**Başarısızlık:** 

Eğer hücrelerin %80’i kurursa ajan başarısız sayılır ve episode sonlandırılır. Bu seviyeye ulaşmak için hücrelerin %80 ve üzerinin nem oranının 20% değerinin altında veya %90 değerinin üzerinde olması gerekmektedir. 

%20-40 aralığı ile %70-90 aralık değerleri doğrudan bir hücrenin başarılı veya başarısız sayılmaması için bir buffer görevi görmektedir.

**Maksimum adım:** 

Bir bölüm için belirlenen maksimum adım sayısına (step/iteration) ulaşılırsa o bölüm, başarı veya başarısızlık durumundan bağımsız olarak sonlandırılır.

5x5 grid içerisinde toplam 25 hücre (bitki) olduğundan her birine yeterli keşif yapılabilmesi için gerekli olan bölüm başına maksimum adım sayısının da buna uyacak şekilde yüksek tutulması, öğrenme performansını olumlu etkiler.

## Ödül Sistemi (Positive/Negative Rewards)

- Robotu harekete geçmeye teşvik eden başlangıç ödül değeri -0.1’dir.
- Başarılı Bitiş koşulu sağlanırsa robot +1000 ödül alırken, Başarısız Bitiş koşulu sağlanırsa -500 ödül alır.
- Robotun kuru bir hücreye su vermeden veya fazla ıslak bir hücreyi kurutmadan hücreden ayrılması robotun -5 ödül almasına sebep olur.
- Eğer robot, ideal bir hücreye su vermeden veya hücredeki suyu kurutmadan başka bir hücreye geçerse harekete teşvik amaçlı +1 ödül verilir.
- Nem seviyesi yeterli bir hücreyi sulamak veya kurutmaya gerek olmayan bir hücreyi kurutmak robota -5 ödül kazandırır.
- Duvara vurmanın ödülü -1’dir.

## Encode Fonksiyonu

Encode fonksiyonu ajan pozisyonunu, hava durumunu ve de ajanın bulunduğu hürenin nem miktarını tutan indeks değerlerini alarak çok boyutlu bir adresi, tek bir ID değerine çevirir. Bu ID değeri Q tablosuna eklenerek ajanın fiziksel pozisyonuyla birlikte ajanın görebildiği o anki durumun (state) tamamını ifade eder ve ajanın bir sonraki hareketi yapması için karar mekanizmasında kullanılır.

## Ortam Simülasyonu

Gerek eğitim sürecindeki bölümlerin gerek test sürecindeki bölümlerin hareketleri, grid içerisinde her bir bileşen farklı renklerle gösterilerek animasyon şeklinde görüntülenebilir. Amaç yeşil hücreleri en yüksek tutarak, kahverengi ve mavi hücrelerden kurtulmaktır. Yeşilden kahverengine veya maviye geçişler ise ara tonlarla gösterilerek hücrelerdeki değişim durumlarını belirtir.

**Örnek Bir Test Simülasyonu**

![validation_run-0.gif](./validation_run-0.gif)