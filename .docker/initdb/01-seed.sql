--
-- PostgreSQL database dump
--

\restrict YPCP9CpbG0Vjjk2pwx25KZ9oRTbaLURmLzhgdwrNEBdaTJnL6Aml2ouFL4ZuELy

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.transcripts DROP CONSTRAINT IF EXISTS transcripts_user_id_meeting_id_fkey;
ALTER TABLE IF EXISTS ONLY public.next_meeting_reports DROP CONSTRAINT IF EXISTS next_meeting_reports_user_id_patient_id_fkey;
ALTER TABLE IF EXISTS ONLY public.next_meeting_reports DROP CONSTRAINT IF EXISTS next_meeting_reports_user_id_meeting_id_fkey;
ALTER TABLE IF EXISTS ONLY public.meeting_summaries DROP CONSTRAINT IF EXISTS meeting_summaries_user_id_meeting_id_fkey;
DROP INDEX IF EXISTS public.ix_users_email;
DROP INDEX IF EXISTS public.ix_transcripts_meeting_id;
DROP INDEX IF EXISTS public.ix_next_meeting_reports_user_patient;
DROP INDEX IF EXISTS public.ix_next_meeting_reports_meeting_id;
DROP INDEX IF EXISTS public.ix_meeting_summaries_meeting_id;
DROP INDEX IF EXISTS public.ix_calendar_events_user_start_at;
DROP INDEX IF EXISTS public.ix_calendar_events_user_end_at;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.transcripts DROP CONSTRAINT IF EXISTS uq_transcripts_user_meeting;
ALTER TABLE IF EXISTS ONLY public.meeting_summaries DROP CONSTRAINT IF EXISTS uq_summaries_user_meeting;
ALTER TABLE IF EXISTS ONLY public.next_meeting_reports DROP CONSTRAINT IF EXISTS uq_reports_user_meeting;
ALTER TABLE IF EXISTS ONLY public.transcripts DROP CONSTRAINT IF EXISTS transcripts_pkey;
ALTER TABLE IF EXISTS ONLY public.patients DROP CONSTRAINT IF EXISTS patients_pkey;
ALTER TABLE IF EXISTS ONLY public.next_meeting_reports DROP CONSTRAINT IF EXISTS next_meeting_reports_pkey;
ALTER TABLE IF EXISTS ONLY public.meeting_summaries DROP CONSTRAINT IF EXISTS meeting_summaries_pkey;
ALTER TABLE IF EXISTS ONLY public.calendar_events DROP CONSTRAINT IF EXISTS calendar_events_pkey;
DROP TABLE IF EXISTS public.users;
DROP TABLE IF EXISTS public.transcripts;
DROP TABLE IF EXISTS public.patients;
DROP TABLE IF EXISTS public.next_meeting_reports;
DROP TABLE IF EXISTS public.meeting_summaries;
DROP TABLE IF EXISTS public.calendar_events;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: calendar_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calendar_events (
    user_id uuid NOT NULL,
    id uuid NOT NULL,
    title character varying(255) NOT NULL,
    description character varying(2000),
    start_at timestamp with time zone NOT NULL,
    end_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    patient_id uuid
);


--
-- Name: meeting_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meeting_summaries (
    user_id uuid NOT NULL,
    id uuid NOT NULL,
    meeting_id uuid NOT NULL,
    status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    text text,
    model character varying(64) DEFAULT ''::character varying NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: next_meeting_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.next_meeting_reports (
    user_id uuid NOT NULL,
    id uuid NOT NULL,
    patient_id uuid NOT NULL,
    meeting_id uuid NOT NULL,
    status character varying(16) DEFAULT 'pending'::character varying NOT NULL,
    intro text,
    changes jsonb NOT NULL,
    open_topics jsonb NOT NULL,
    source_meeting_ids jsonb NOT NULL,
    model character varying(64) DEFAULT ''::character varying NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    user_id uuid NOT NULL,
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    phone character varying(32) NOT NULL,
    email character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: transcripts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcripts (
    user_id uuid NOT NULL,
    id uuid NOT NULL,
    meeting_id uuid NOT NULL,
    raw_text text NOT NULL,
    diarized_segments jsonb NOT NULL,
    language character varying(16) DEFAULT 'he'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    auth_type character varying(64) NOT NULL,
    role character varying(64) NOT NULL,
    email character varying(255),
    full_name character varying(255),
    password_hash character varying(512),
    token_version integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Data for Name: calendar_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calendar_events (user_id, id, title, description, start_at, end_at, created_at, patient_id) FROM stdin;
3fa85f64-5717-4562-b3fc-2c963f66afa6	4baad938-131e-5175-99f1-fc75d0db0925	מפגש 1: יצירת קשר, זיהוי קהות רגשית ומנגנון הריצה	\N	2026-06-16 11:00:00+00	2026-06-16 11:50:00+00	2026-06-16 11:00:00+00	440b1050-05f7-5b43-9162-635bd9cca81f
3fa85f64-5717-4562-b3fc-2c963f66afa6	139b6dca-e267-5755-a52f-8ef7dfa56dfb	מפגש 2: מיפוי טריגרים חושיים ועבודה על חלון העוררות	\N	2026-06-23 11:00:00+00	2026-06-23 11:50:00+00	2026-06-23 11:00:00+00	440b1050-05f7-5b43-9162-635bd9cca81f
3fa85f64-5717-4562-b3fc-2c963f66afa6	44a49a3f-7861-5db1-8a4e-a1f5195f32dd	מפגש 3: כניסה לעבודת אבל וקבלה דרך גישת טיפול בקבלה ומחויבות	\N	2026-06-30 11:00:00+00	2026-06-30 11:50:00+00	2026-06-30 11:00:00+00	440b1050-05f7-5b43-9162-635bd9cca81f
3fa85f64-5717-4562-b3fc-2c963f66afa6	f2ef5ca4-9070-5548-818b-594741bcc5a1	מפגש 4: עיבוד הזיכרון הטראומטי והפחתת מטען רגשי	\N	2026-07-07 11:00:00+00	2026-07-07 11:50:00+00	2026-07-07 11:00:00+00	440b1050-05f7-5b43-9162-635bd9cca81f
3fa85f64-5717-4562-b3fc-2c963f66afa6	e3fef676-6b55-502a-ac11-4b77d413317b	מפגש 5: אינטגרציה, פרידה מהאבל וצמיחה פוסט-טראומטית	\N	2026-07-14 11:00:00+00	2026-07-14 11:50:00+00	2026-07-14 11:00:00+00	440b1050-05f7-5b43-9162-635bd9cca81f
3fa85f64-5717-4562-b3fc-2c963f66afa6	c1b7c9c5-bd37-597c-ba13-a38515d91d06	מפגש 1: ברית טיפולית, מיפוי עוררות היתר וההסתגרות	\N	2026-06-16 13:00:00+00	2026-06-16 13:50:00+00	2026-06-16 13:00:00+00	b80b1ab1-5d45-520f-897c-b1ddf51e9713
3fa85f64-5717-4562-b3fc-2c963f66afa6	6cb461fe-7295-5a2f-afe7-34d9f31d67e1	מפגש 2: פסיכו-אדיוקציה ועבודה קוגניטיבית על אמונות יסוד	\N	2026-06-23 13:00:00+00	2026-06-23 13:50:00+00	2026-06-23 13:00:00+00	b80b1ab1-5d45-520f-897c-b1ddf51e9713
3fa85f64-5717-4562-b3fc-2c963f66afa6	0474e95e-060b-5edd-b44c-c02761a27341	מפגש 3: הכנת משאבים ויצירת מקום בטוח	\N	2026-06-30 13:00:00+00	2026-06-30 13:50:00+00	2026-06-30 13:00:00+00	b80b1ab1-5d45-520f-897c-b1ddf51e9713
3fa85f64-5717-4562-b3fc-2c963f66afa6	ee1a66c6-5096-57eb-ac18-72e95deb9511	מפגש 4: עיבוד חושי בתנועות עיניים של טראומת הילדות	\N	2026-07-07 13:00:00+00	2026-07-07 13:50:00+00	2026-07-07 13:00:00+00	b80b1ab1-5d45-520f-897c-b1ddf51e9713
3fa85f64-5717-4562-b3fc-2c963f66afa6	499f468b-a7f4-5e8e-8f2a-069bb9786bfc	מפגש 5: אינטגרציה, פתיחות לקשר וצמיחה	\N	2026-07-14 13:00:00+00	2026-07-14 13:50:00+00	2026-07-14 13:00:00+00	b80b1ab1-5d45-520f-897c-b1ddf51e9713
3fa85f64-5717-4562-b3fc-2c963f66afa6	ba7327d2-5aa1-5248-b48d-4c84bc97be4c	מפגש 1: ברית טיפולית, הערכה ראשונית ומיפוי ההימנעות	\N	2026-06-16 09:00:00+00	2026-06-16 09:50:00+00	2026-06-16 09:00:00+00	7f5bdcd5-baf5-56e1-982a-a0c56310dd60
3fa85f64-5717-4562-b3fc-2c963f66afa6	f1a41efe-6dc9-596f-9166-b2a9a6985fe6	מפגש 2: פסיכו-אדיוקציה ובניית משאבים למקום בטוח	\N	2026-06-23 09:00:00+00	2026-06-23 09:50:00+00	2026-06-23 09:00:00+00	7f5bdcd5-baf5-56e1-982a-a0c56310dd60
3fa85f64-5717-4562-b3fc-2c963f66afa6	aa83077a-19ed-5d1d-9bc8-4f428993e8c2	מפגש 3: זיהוי נקודות תקיעה ואיתגור אשמה	\N	2026-06-30 09:00:00+00	2026-06-30 09:50:00+00	2026-06-30 09:00:00+00	7f5bdcd5-baf5-56e1-982a-a0c56310dd60
3fa85f64-5717-4562-b3fc-2c963f66afa6	f1e8f410-53a6-5843-bc89-8037ea308a14	מפגש 4: שלב העיבוד החושי בעיבוד מחדש והטמעה	\N	2026-07-07 09:00:00+00	2026-07-07 09:50:00+00	2026-07-07 09:00:00+00	7f5bdcd5-baf5-56e1-982a-a0c56310dd60
3fa85f64-5717-4562-b3fc-2c963f66afa6	b05b45ef-5564-5f2e-885e-47f1e7e1bf66	מפגש 5: אינטגרציה, החזרת הסמכות ויציאה מהימנעות	\N	2026-07-14 09:00:00+00	2026-07-14 09:50:00+00	2026-07-14 09:00:00+00	7f5bdcd5-baf5-56e1-982a-a0c56310dd60
\.


--
-- Data for Name: meeting_summaries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.meeting_summaries (user_id, id, meeting_id, status, text, model, error, created_at, updated_at) FROM stdin;
3fa85f64-5717-4562-b3fc-2c963f66afa6	8b742108-8106-5380-8e09-fb13f3824f3a	4baad938-131e-5175-99f1-fc75d0db0925	ready	אוקיי, סיכום פגישה ראשונה עם פורסט. לקח קצת זמן לייצר איתו חיבור, אבל הוא שיתף פעולה בצורה יוצאת דופן. פורסט מציג תמונה קלאסית של קהות רגשית – הוא מדבר על אירועים קטסטרופליים, כמו המארב בווייטנאם והמוות של באבה, בטון אחיד, שטוח, כאילו הוא מקריא ספר היסטוריה. אין לו שום חיבור לחוויה הגופנית של הפחד. כשניסיתי לשהות איתו קצת ברגע של האובדן, הוא מיד תיאר איך הוא פשוט התחיל לרוץ בלי סיבה מיוחדת ולא הפסיק במשך חודשים. זיהינו יחד שהריצה שלו היא למעשה מנגנון הימנעות קומפולסיבי שנועד להרחיק אותו מההצפה הרגשית. לקראת הפגישה הבאה: המטרה היא בעיקר פסיכו-אדיוקציה על הקשר בין הריצה הפיזית לבין הבריחה מהרגש, ולבקש ממנו רק לשים לב מתי עולה בו הדחף החזק לצאת לדרך.	seed	\N	2026-06-16 11:00:00+00	2026-06-16 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	bc8ed42c-a891-5d00-bbb8-59dd64b9be6d	139b6dca-e267-5755-a52f-8ef7dfa56dfb	ready	סיכום מפגש שני עם פורסט. השבוע היה מאתגר עבורו בגלל מזג האוויר. מסתבר שהיה לילה של גשם סוער, וזה פעל אצלו כטריגר חושי ישיר שהחזיר אותו למונסונים בוייטנאם. הוא חווה פלאשבקים חזקים של ריח הבוץ והקולות של הפצועים. במקום לרוץ, הוא מצא את עצמו נכנס למצב של קפיאה וניתוק – הוא פשוט ישב שעות על הספסל בלי לזוז, מה שמראה שהוא יצא לחלוטין מחלון העוררות שלו לכיוון של תת-עוררות. עבדנו היום חזק על טכניקות של קרקוע חושי – להחזיק חפצים, להרגיש את הרצפה, להשתמש בחושים כדי להזכיר למוח שהוא פה בכיסא עכשיו ולא בג'ונגל. לפעם הבאה: תרגלנו פרוטוקול נשימות ועגינה, והוא קיבל משימה להשתמש בזה אם הגשם יחזור, כדי לנסות להישאר בתוך החלון המוגן.	seed	\N	2026-06-23 11:00:00+00	2026-06-23 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	5eb71aff-d665-59b1-8e77-d927a2141cb9	44a49a3f-7861-5db1-8a4e-a1f5195f32dd	ready	טוב, סיכום פגישה שלישית עם פורסט. היום עשינו עבודה עמוקה מאוד דרך עקרונות של טיפול בקבלה ומחויבות. עבדנו על המושג של קבלה חווייתית – היכולת לתת מקום לרגש כואב מבלי לנסות להילחם בו או לברוח ממנו. פורסט החזיק המון זמן את התפיסה שהוא חייב להיות חזק ולהמשיך הלאה, ופירקנו את זה. פתחנו את קופסת הזיכרונות של באבה ושל אמא שלו. לראשונה, הוא הרשה לעצמו להראות עצב חריף בקליניקה. הוא בכה, הראה חיבור רגשי אמיתי, והצלחנו לשהות שם בלי שהוא יתנתק ובלי שהוא ירגיש דחף לקום ולרוץ. זה היה צעד ענק בהרחבת היכולת שלו להכיל כאב. לפעם הבאה: נרצה לעקוב אחרי רמת החרדה שלו בימים שאחרי המפגש, ולראות אם פתיחת השער הזה לאבל העלתה תסמינים חודרניים.	seed	\N	2026-06-30 11:00:00+00	2026-06-30 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	bf0277fa-7730-5568-9a2e-fc0dc8f925b0	f2ef5ca4-9070-5548-818b-594741bcc5a1	ready	סיכום פגישה רביעית. היום חזרנו לרגע המארב בווייטנאם – הרגע שבו הוא רץ תחת אש לתוך הג'ונגל פעם אחר פעם כדי להציל את החברים מהמחלקה, עד שמצא את באבה פצוע אנוש. השתמשנו בעיבוד ממוקד כדי לפרק את הזיכרון לרכיבים החושיים שלו כמו החום, הצעקות וריח השריפה. ראינו שיש לו המון אשמה סמויה על כך שלא הצליח להציל את באבה למרות הכל. עשינו הבניה מחדש של הסיטואציה כדי להדגיש את העובדה שהוא פעל בגבורה עילאית ושחוסר האונים מול הפציעה הקטלנית היה גזירת גורל, לא כישלון שלו. מדד המצוקה הרגשית שלו ירד באופן משמעותי לקראת סוף המפגש, והוא דיווח על תחושת הקלה פיזית בחזה. לפעם הבאה: להמשיך לעקוב אחרי הזיכרון הספציפי הזה ולראות אם רמת החודרנות שלו פחתה.	seed	\N	2026-07-07 11:00:00+00	2026-07-07 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	98a57485-9f66-55cf-9f83-bda70bc36808	e3fef676-6b55-502a-ac11-4b77d413317b	ready	מפגש חמישי וסיכום שלב עם פורסט. היום עשינו עבודה מדהימה של אינטגרציה ויצירת נרטיב חיים שלם. פורסט שיתף שהוא הלך השבוע לבקר בקבר של באבה ושל ג'ני, אבל הפעם החוויה הייתה שונה – הוא הרגיש עצב עמוק וגעגוע, אבל לא את הפאניקה והדריכות הקבועות של הטראומה. הוא אמר משפט יפה: 'אני כבר לא צריך לרוץ כדי להשאיר את הזיכרונות מאחור, אני יכול ללכת איתם'. זה סימן מובהק לתהליך של צמיחה פוסט-טראומטית. הוא מתחיל לגלות מעורבות רגשית גדולה יותר בקהילה ובקשרים שלו. לקראת מפגשי המעקב הבאים: נתמקד בשימור ההישגים, הרחבת מעגלי התמיכה החברתיים שלו, ווידוא שהוא ממשיך להשתמש בכלים של הקרקוע כשהוא פוגש טריגרים בשגרה.	seed	\N	2026-07-14 11:00:00+00	2026-07-14 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	a43e5481-57c1-5c73-9a36-dd744c7d1043	c1b7c9c5-bd37-597c-ba13-a38515d91d06	ready	אוקיי, סיכום פגישה ראשונה עם הארי. המפגש היום התאפיין בהמון חשדנות, ולקח זמן לפצח את החומות שלו. הארי מציג תמונה קלאסית של עוררות יתר קיצונית – הוא ישב דרוך, סרק את החלונות והדלת בקליניקה, ודיווח על אינסומניה קשה וסיוטים. כיוון שמדובר בטראומה מורכבת שיושבת על רקע של הזנחה והתעללות מתמשכת בילדות, יש לו קושי עמוק לתת אמון בעולם ובאנשים. הוא שיתף שהשבוע הוא הדף בצורה חריפה את רון והרמיוני כשהם ניסו להתקרב ולהציע עזרה. זיהינו יחד שההסתגרות שלו היא מנגנון הגנה שנועד לנהל את החרדה, מתוך מחשבה מעוותת שאם אני ארחיק אותם, הם לא ייפגעו בגללי. לקראת הפגישה הבאה: המטרה היא להמשיך לבסס את הברית הטיפולית כמרחב בטוח, בלי ללחוץ עליו, ולבקש ממנו רק לשים לב מתי עולה בו הדחף האוטומטי להדוף את הקרובים אליו.	seed	\N	2026-06-16 13:00:00+00	2026-06-16 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	a2c3fe67-8669-594f-be5a-7a0fa031c501	6cb461fe-7295-5a2f-afe7-34d9f31d67e1	ready	סיכום מפגש שני עם הארי. היום עשינו עבודה משמעותית על פסיכו-אדיוקציה לגבי טראומה מורכבת. הסברתי לו איך מערכת העצבים שלו למדה להיות במצב הישרדותי קבוע בארון מתחת למדרגות, ואיך הגוף שלו ממשיך להפריש אדרנלין גם כשהסכנה המיידית חלפה. זה עזר לו להבין את המקור של הדריכות הגופנית שלו. משם עברנו למיפוי נקודות תקיעה קוגניטיביות לגבי המושגים של בטיחות ואמון. ניסחנו את אמונת היסוד המרכזית שלו: העולם הוא מקום מסוכן לחלוטין, ואני תמיד חייב להילחם לבד. התחלנו לאתגר את ההנחה הגורפת הזו ולחפש יוצאים מן הכלל – רגעים שבהם הישענות על אחרים דווקא הצילה אותו. לפעם הבאה: ביקשתי ממנו לנסות לעשות ניסוי התנהגותי קטן, ולאפשר לרון או הרמיוני לעזור לו במטלה קטנה אחת בשגרה, בלי להדוף אותם, ולראות מה קורה לחרדה.	seed	\N	2026-06-23 13:00:00+00	2026-06-23 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	87602874-b0e0-5646-9004-c611b67a58a7	0474e95e-060b-5edd-b44c-c02761a27341	ready	טוב, סיכום פגישה שלישית עם הארי. הניסוי ההתנהגותי מהשבוע שעבר עבר בהצלחה חלקית – הוא איפשר להרמיוני לעזור לו עם איזו משימה, אבל דיווח על הצפה רגשית מיד לאחר מכן ותחושת אובדן שליטה. הבנתי שאנחנו חייבים לחזק משאבי ויסות בגוף לפני שנמשיך. היום עבדנו על פרוטוקול הכנת משאבים לעיבוד בתנועות עיניים. בנינו יחד את המקום הבטוח שלו. היה לו קשה מאוד למצוא מקום כזה בעולם האמיתי, אבל בסוף הוא בחר בחדר המועדון של גריפינדור ליד האח – מקום עם חמימות, חברים ברקע, אבל בלי סכנה מיידית. הטמענו את התחושה הגופנית הזו באמצעות גירוי דו-צדדי איטי, ותרגלנו גם טכניקות קרקוע כמו נשימות מרובעות כדי לעזור לו לנהל את עוררות היתר כשהוא בציבור. לפעם הבאה: לתרגל את הכניסה למקום הבטוח בכל פעם שרמת העוררות עולה מעל לחלון העוררות שלו.	seed	\N	2026-06-30 13:00:00+00	2026-06-30 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	d9b69da4-7e18-5f28-986d-d13be20c8f22	ee1a66c6-5096-57eb-ac18-72e95deb9511	ready	סיכום פגישה רביעית עם הארי, מפגש קשה אך פורץ דרך. הרגשתי שהמשאבים יציבים מספיק כדי לגשת לטראומת הבסיס החוזרת. הלכנו לזיכרון של הארון החשוך מתחת למדרגות – הרגע שבו נועלים אותו שם בפנים כילד קטן, מנותק, חסר אונים ומוזנח. הקוגניציה השלילית שהגדרנו הייתה אני פגום, מגיע לי להיות לבד, והתחושה בגוף הייתה מחנק חריף בחזה ותחושת כיווץ בגפיים. התחלנו עיבוד מחדש עם גירוי דו-צדדי מהיר. חווינו מהר מאוד הצפה רגשית חזקה, עלו זיכרונות של צעקות ותחושת הכלואה, אבל החזקנו את זה בתוך חלון העוררות. לאט לאט המטען החל להשתנות, והוא הצליח להביא חמלה לילד הקטן שהיה שם. הקוגניציה התחילה לזוז לכיוון של אני שרדתי, וזה לא היה באשמתי. סיימנו עם סגירה קפדנית דרך המקום הבטוח. לפעם הבאה: מעקב הדוק אחרי איכות השינה והסיוטים השבוע בעקבות פתיחת זיכרון הילדות.	seed	\N	2026-07-07 13:00:00+00	2026-07-07 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	09c5b306-2aec-57d1-a581-9e9d6f6f6737	499f468b-a7f4-5e8e-8f2a-069bb9786bfc	ready	סיכום פגישה חמישית. הארי הגיע היום במצב שונה לגמרי – הוא שיתף שהשבוע, לראשונה מזה חודשים, הוא ישן ארבעה לילות ברצף ללא סיוטים חודרניים. רמת עוררות היתר הגופנית שלו ירדה בצורה ניכרת, והוא ישב נינוח יותר על הכיסא. הוא סיפר שקיים שיחה פתוחה עם רון והרמיוני, שיתף אותם בחלק מהתחושות שלו ולא הרגיש צורך אקטיבי לבצע הסתגרות. זהו שלב מדהים של אינטגרציה, שבו הוא מתחיל להבין שהעבר שלו בארון הוא סיפור קשה שהוא סוחב, אבל הוא לא מגדיר את מי שהוא בהווה. אנחנו רואים כאן ניצנים ברורים של צמיחה פוסט-טראומטית והסכמה לקבל תמיכה. לקראת מפגשי ההמשך: נתמקד בביסוס מערכות היחסים, עיבוד של זיכרונות אקוטיים מאוחרים יותר כמו הקרבות הבוגרים, ושימור תחושת המוגנות בקשר הטיפולי ומחוצה לו.	seed	\N	2026-07-14 13:00:00+00	2026-07-14 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	c715187c-de35-569b-aaee-a7a2b1915ab5	ba7327d2-5aa1-5248-b48d-4c84bc97be4c	ready	אוקיי, סיכום פגישה ראשונה עם סימבה. המטרה היום הייתה בעיקר יצירת ברית והערכה ראשונית. הוא הגיע מאוד סגור וחשדן, גוף דרוך מאוד, סרק את הקליניקה ללא הפסקה – חיווי ברור של עוררות יתר. כשניסיתי לגעת בעבר שלו ובסיבת העזיבה של ארץ התקווה, הוא מיד הפעיל מנגנון של הימנעות חריף וזרק את המשפט 'האקונה מטאטה'. הוא ממש משתמש בזה כדפוס נוקשה של קהות רגשית כדי לא לחוש את הכאב. לקראת סוף המפגש הוא הודה שהמפגש עם נאלה פוצץ את הבועה הזו והוא כבר לא מצליח להדחיק. סיכמנו שהמטרה שלנו היא לא לשכוח את העבר, אלא ללמוד לחיות איתו בלי שהוא ינהל אותו. לפעם הבאה: נמשיך לבסס את תחושת המוגנות בקשר, ונבקש ממנו רק לשים לב מתי השבוע הוא מרגיש את הדחף הפיזי לברוח או להתנתק.	seed	\N	2026-06-16 09:00:00+00	2026-06-16 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	7aa64728-9ff9-5a2a-80c5-109e7894cafd	f1a41efe-6dc9-596f-9166-b2a9a6985fe6	ready	סיכום פגישה שנייה עם סימבה. היום עשינו עבודה מצוינת על פסיכו-אדיוקציה. הסברתי לו מה קורה לו בגוף כשהוא נבהל מרעשים חזקים – כמו הרעם שהיה השבוע – ואיך המוח שלו מפרש את זה כאילו הוא עדיין פיזית בתוך האסון של עדר הגנו בקניון. זה מאוד הרגיע אותו להבין שהוא לא משתגע, אלא שזו תגובה נורמלית למצב לא נורמלי. משם עברנו להכנת משאבים לקראת עיבוד עתידי בהטמעת תנועות עיניים. בנינו יחד את המקום הבטוח שלו. הוא בחר בנווה המדבר שבו חי עם טימון ופומבה – מקום עם מים זורמים, שקט, בלי דרישות. תרגלנו את זה עם גירוי דו-צדדי איטי כדי להטמיע את תחושת הרוגע בגוף. לפעם הבאה: הוא קיבל משימה לתרגל את הכניסה למקום הבטוח הזה בבית בכל פעם שהוא מרגיש את רמת החרדה עולה.	seed	\N	2026-06-23 09:00:00+00	2026-06-23 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	6da2e6c4-39f0-5cfe-a026-7b21c59ffa23	aa83077a-19ed-5d1d-9bc8-4f428993e8c2	ready	טוב, סיכום פגישה שלישית. נכנסנו היום לעומק של פרוטוקול טיפול בעיבוד קוגניטיבי. הצלחנו לנסח בצורה חדה את נקודת התקיעה המרכזית שלו שמנהלת לו את החיים: 'אני הרגתי את אבא שלי, כי אם לא הייתי מנסה לשאוג בקניון העדר לא היה נבהל ומופאסה לא היה צריך להציל אותי'. ראינו כמה אשמה ובושה נוקשות יושבות שם. התחלנו לעשות פונקציה של איתגור קוגניטיבי – בחנו את העובדות האובייקטיביות. שאלתי אותו אם לגור אריות קטן יש בכלל יכולת פיזית לנהל תנועה של עדר שלם, והתחלנו להפריד בין השפעה לבין אחריות ובין כוונה לתוצאה. הוא בכה המון, היה קושי גדול לשחרר את השליטה, כי לקבל את זה שהוא לא אשם אומר לקבל את העובדה שהוא היה פשוט חסר אונים באותו רגע. לפעם הבאה: נמשיך לעבוד על דף המחשבות ולפרק את האמונה הזו, ולראות איך הגוף מגיב להפרדה הזו בין אשמה לחוסר אונים.	seed	\N	2026-06-30 09:00:00+00	2026-06-30 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	7e6a3192-1e42-59f6-8337-87955fc0a695	f1e8f410-53a6-5843-bc89-8037ea308a14	ready	פגישה רביעית עם סימבה, מפגש דרמטי ומשמעותי מאוד. אחרי שהבסיס הקוגניטיבי היה יציב יותר, הרגשתי שאפשר להתחיל בעיבוד הישיר של זיכרון הטראומה בתנועות עיניים. הלכנו לתמונה הקשה ביותר עבורו – הרגע שבו האבק שוקע בקניון והוא מוצא את הגוף של מופאסה ולא מצליח להעיר אותו. הקוגניציה השלילית הייתה 'אני חסר אונים ופגום', והתחושה בגוף הייתה מחנק מטורף בגרון וכובד בחזה. עבדנו עם גירוי דו-צדדי אינטנסיבי. בהתחלה הייתה הצפה חזקה מאוד, הוא ממש שמע את רעש הדהירה של הפרסות, אבל לאט לאט, עם הסטים החוזרים, המטען הרגשי החל לרדת. הוא התחיל לראות את התמונה מזווית אחרת, חמלה כלפי עצמו כגור קטן. עצרנו כשרמת המצוקה ירדה משמעותית, ועשינו סגירה מסודרת עם המקום הבטוח. לפעם הבאה: לבדוק אם יש אפקט גלישה של העיבוד השבוע כמו סיוטים או תובנות חדשות ולראות איפה מדד המצוקה עומד.	seed	\N	2026-07-07 09:00:00+00	2026-07-07 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	260cc300-cd31-5bfa-81c6-b43d46f7a11b	b05b45ef-5564-5f2e-885e-47f1e7e1bf66	ready	סיכום פגישה חמישית ואחרונה ברצף הנוכחי עם סימבה. היום עשינו בעיקר אינטגרציה וסיכום תהליך. הוא הגיע במצב שונה לחלוטין – הגוף משוחרר יותר, היציבה זקופה, הוא יוצר קשר עין רציף. הוא שיתף שהשבוע הוא הצליח להביט למעלה אל כוכבי השמיים בלי להרגיש את תחושת המחנק הרגילה, והרגיש חיבור חיובי לדמות של אבא שלו, ולא רק דרך הטראומה. בדקנו את נקודת התקיעה הישנה, והוא אמר בפירוש: 'אני מבין היום שצלק ניצל את האסון, ואני הייתי רק ילד שרצה לשרוד'. הוא קיבל החלטה אקטיבית לסיים את תקופת ההימנעות במדבר ולחזור לארץ התקווה כדי לקחת אחריות על החיים שלו ועל הממלכה. זו פריצת דרך קלינית מדהימה של מעבר מטראומה לצמיחה פוסט-טראומטית. לקראת המפגש הבא שיהיה כבר מפגש מעקב מרוחק: נבדוק איך הוא מתמודד עם החזרה הפיזית לסביבה המקורית ואיך הוא מחזיק את הגבולות שלו מול אתגרי המציאות החדשים.	seed	\N	2026-07-14 09:00:00+00	2026-07-14 09:00:00+00
\.


--
-- Data for Name: next_meeting_reports; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.next_meeting_reports (user_id, id, patient_id, meeting_id, status, intro, changes, open_topics, source_meeting_ids, model, error, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: patients; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.patients (user_id, id, name, phone, email, created_at) FROM stdin;
3fa85f64-5717-4562-b3fc-2c963f66afa6	440b1050-05f7-5b43-9162-635bd9cca81f	פורסט	+972-50-7654321	\N	2026-06-16 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	b80b1ab1-5d45-520f-897c-b1ddf51e9713	הארי	+972-50-9998887	\N	2026-06-16 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	7f5bdcd5-baf5-56e1-982a-a0c56310dd60	סימבה	+972-50-1234567	\N	2026-06-16 09:00:00+00
\.


--
-- Data for Name: transcripts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.transcripts (user_id, id, meeting_id, raw_text, diarized_segments, language, created_at) FROM stdin;
3fa85f64-5717-4562-b3fc-2c963f66afa6	27f33416-a345-57eb-bab8-4c21ac8aaeec	4baad938-131e-5175-99f1-fc75d0db0925	הפער בין התיאורים הגרפיים של הקרב לבין הטון המונוטוני שלו הוא עצום — קהות רגשית מובהקת. הריצה שלו היא לא פעילות גופנית, היא הימנעות פיזית ואקטיבית שמסייעת לו לברוח מחומרי הזיכרון הבלתי מעובדים. המטרה הראשונית בפסיכו-אדיוקציה תהיה להסביר לו בעדינות שהגוף שלו מנסה להוריד את הווליום של הכאב דרך הרגליים, ולעזור לו להתחיל להבחין בדחף הזה לפני שהוא פשוט קם ורץ.	[]	he	2026-06-16 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	2ee8f1c0-ec8c-5209-8506-6c5c3606f97e	139b6dca-e267-5755-a52f-8ef7dfa56dfb	מעניין לראות שכשהוא לא יכול להפעיל את הריצה, הוא קורס ישירות לתוך קפיאה ותת-עוררות קיצונית. הגשם השבוע זרק אותו החוצה מחלון העוררות בצורה חריפה. תרגלנו המון קרקוע פיזי כדי להחזיר אותו אל הכאן ועכשיו בקליניקה. לפעם הבאה, הפידבק של סנסיי בדוח ההכנה צריך להתמקד בבדיקת היעילות של טכניקות הקרקוע האלו במציאות הביתית שלו.	[]	he	2026-06-23 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	fa844e3a-142f-57cc-8fd9-cb3c5d91ea2f	44a49a3f-7861-5db1-8a4e-a1f5195f32dd	עבודת הטיפול בקבלה ומחויבות הניבה היום פריצת דרך רגשית. השהייה בתוך הקבלה החווייתית אפשרה לו, אולי לראשונה, לא לעשות שום מניפולציה על האבל שלו — לא לרוץ ולא לקפוא, פשוט לבכות. הפירוק של הציפייה העצמית שלו להיות חזק החזיר לו את האנושיות. עם זאת, פתיחת סכר האבל על באבה ועל אמו דורשת משנה זהירות; צריך לוודא שאין השבוע הצפה חודרנית חריפה מחוץ לקליניקה.	[]	he	2026-06-30 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	0b5d0eb4-ceb3-52eb-a1c7-3b7686583700	f2ef5ca4-9070-5548-818b-594741bcc5a1	נכנסנו לליבת אירוע הקרב. זיהינו אשמה סמויה וכבדה מאוד, שיושבת על פער הציפיות שלו מעצמו — הוא הציל חצי מחלקה, אבל מבחינתו הוא נכשל כי באבה מת. העבודה על הבניית חוסר האונים כגזירת גורל אובייקטיבית עזרה לו להרפות מההלקאה העצמית. ההקלה הפיזית בחזה בסיום המפגש היא אינדיקטור מצוין להפחתת המטען הרגשי. במפגש הבא נעשה אינטגרציה ונבחן את תפיסת הסיפור כולו.	[]	he	2026-07-07 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	5609c086-6040-5931-8781-f684f28843ca	e3fef676-6b55-502a-ac11-4b77d413317b	החלק המדהים באינטגרציה היה המשפט שלו על הליכה במקום ריצה — זו מטאפורה קלינית מושלמת לצמיחה פוסט-טראומטית. פרידת האבל הבריאה שביצע בקברים של באבה וג'ני מעידה שהטראומה הפכה לנרטיב חיים ולא לפצע פתוח ומציף. במפגשי המעקב נשגיח על שימור היציבות, החיבורים החברתיים החדשים שלו, ונוודא שהוא שומר על ארגז כלי הקרקוע שלו זמין.	[]	he	2026-07-14 11:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	237be401-7b7a-5e9e-b3a9-f1c6aa62d47d	c1b7c9c5-bd37-597c-ba13-a38515d91d06	העבודה עם הארי הולכת להיות ארוכה ומבוססת קשר. החשדנות והסריקה של הקליניקה מעידות על עוררות יתר ברמה הכי גבוהה שפגשתי. מנגנון ההסתגרות שלו נובע מאמונת אשמה מורכבת שהוא מסוכן לסביבה שלו. הברית הטיפולית היא הפיצוח כאן — הוא חייב לחוות את הקשר איתי כמרחב שלא דוחה אותו ולא נפגע ממנו. בשום אופן לא לרוץ קדימה לעיבוד חומרים טראומטיים בשלב זה.	[]	he	2026-06-16 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	13d6c3dc-0010-52b6-a168-9c270ad02a5e	6cb461fe-7295-5a2f-afe7-34d9f31d67e1	החיבור שהוא עשה בין הדריכות הנוכחית לבין הילדות בארון מתחת למדרגות היה חזק. הפסיכו-אדיוקציה נתנה לו מסגרת הגיונית לחוויה הגופנית המשוגעת שלו. נקודת התקיעה של אני חייב להילחם לבד יושבת חזק על חוסר האמון הבסיסי של טראומה מורכבת. הניסוי ההתנהגותי מול רון והרמיוני הוא קריטי, אבל ביקשתי שזה יהיה משהו ממש מינורי כדי לא לייצר הצפה מוקדמת מדי של אובדן שליטה.	[]	he	2026-06-23 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	e72431c2-1597-57b2-a1b6-35e088b9feb8	0474e95e-060b-5edd-b44c-c02761a27341	התגובה שלו לניסוי ההתנהגותי הבהירה לי כמה חלון העוררות שלו צר כרגע. ברגע שהוא פתח פתח קטן לאמון, החרדה פשוט זינקה. טוב שעצרנו הכל ועבדנו על משאבים. בניית המקום הבטוח לקחה זמן, המוח שלו סורק כל מקום לחפש סכנות, אבל הבחירה בחדר המועדון עם האח עבדה מצוין פיזיולוגית. הקרקוע והנשימות הכרחיים בשבילו כדי להחזיר שליטה לגוף.	[]	he	2026-06-30 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	faa50fd2-2576-5951-8bf4-1c2c7d731674	ee1a66c6-5096-57eb-ac18-72e95deb9511	מפגש סוער מאוד. פתחנו את זיכרון הליבה הכי כרוני של הטראומה המורכבת שלו — הארון. החנק בחזה היה מיידי והוא כמעט נכנס לניתוק, אבל הצלחנו להחזיק את המודעות הכפולה בקליניקה. המעבר לקוגניציה חיובית של שרדתי והופעת החמלה העצמית כלפי עצמו כילד היו רגעים קריטיים. בגלל המורכבות של הזיכרון הזה, יש סיכוי גבוה לאפקט גלישה השבוע בסיוטים ובשינה, אז אני זמין עבורו אם תהיה הצפה קיצונית.	[]	he	2026-07-07 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	5c342fc5-9a96-5d0f-a567-dd95654f36cf	499f468b-a7f4-5e8e-8f2a-069bb9786bfc	השיפור באיכות השינה והירידה בעוררות היתר הם הוכחה קלינית מובהקת שהעיבוד של הזיכרון בארון שחרר משהו עמוק במערכת העצבים שלו. האינטגרציה המרשימה ביותר היא היציאה שלו מההסתגרות — העובדה שהוא פתח את הדברים מול החברים שלו מעידה על שינוי ממשי באמונות היסוד שלו על אמון ובטיחות בעולם. במפגשים הבאים נצטרך לעשות אינטגרציה גם לטראומות המאוחרות מהקרבות, כדי להבטיח את שימור הצמיחה הפוסט-טראומטית הזו לאורך זמן.	[]	he	2026-07-14 13:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	9f593628-77f4-520c-9e6c-db820cc4f4ca	ba7327d2-5aa1-5248-b48d-4c84bc97be4c	הוא מציג חזות נוקשה של הכול בסדר, אבל העוררות היתר מטורפת, הוא קופץ מכל רעש במסדרון. השימוש בהאקונה מטאטה הוא ההימנעות הכי קלאסית שראיתי — הגנה קשיחה מפני הצפה. המפגש עם נאלה הוא הטריגר שסדק את הקהות הרגשית, ויש פה חלון הזדמנויות קליני. בשלב זה חשוב לא ללחוץ על הזיכרון בקניון, אלא לבסס את הברית הטיפולית ולעבוד על זיהוי הדחף הגופני לבריחה.	[]	he	2026-06-16 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	35e53fe4-f156-55d5-9bdd-bbf8f940e0e7	f1a41efe-6dc9-596f-9166-b2a9a6985fe6	הפסיכו-אדיוקציה הורידה ממנו המון אשמה ראשונית, הוא הבין שהתגובות שלו לרעם הן ביטוי פיזיולוגי של הטראומה. המקום הבטוח שבחרנו, נווה המדבר, מחובר אצלו חזק לחוויה של היעדר שפיטה, וזה מצוין. הגירוי הדו-צדדי האיטי הצליח להוריד את רמת מדד המצוקה באופן ניכר בקליניקה. נראה אם הוא יצליח ליישם את תרגול הוויסות העצמי הזה בבית כשיעלו טריגרים חזקים.	[]	he	2026-06-23 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	5474917b-8efd-5b1d-9fec-ff3bcdfadfcf	aa83077a-19ed-5d1d-9bc8-4f428993e8c2	המפגש הכי קשה עד כה. נקודת התקיעה שלו מנוסח בצורה אבסולוטית ומעוותת, הוא לוקח אחריות של מבוגר על אירוע קטסטרופלי. הבכי שלו הציף את חוסר האונים העמוק, שהיה חסום תחת מעטה האשמה. האשמה בעצם נתנה לו אשליה של שליטה. האתגר הבא בעיבוד הקוגניטיבי יהיה לבסס את ההבנה שלא הייתה שם כוונה ושאין לו אחריות על התנהגות העדר, כדי להכין את הקרקע לעיבוד החושי הטהור.	[]	he	2026-06-30 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	b8d6bd33-02fc-5f0d-9bc1-ba5bfdb4e467	f1e8f410-53a6-5843-bc89-8037ea308a14	נכנסנו לעיבוד מחדש של זיכרון הליבה החושי. הציפה אותו תחושת חנק פיזית קשה, והסאונד של פרסות הגנו עלה בצורה חריפה. שמרנו על חלון העוררות באמצעות הסטים המהירים. לקראת הסוף ראינו מעבר לקוגניציה חיובית ראשונית וחמלה עצמית. רמת המצוקה ירדה משמעותית בסיום, אבל צריך לעקוב מקרוב השבוע אחרי חלומות או הצפה רגשית מאוחרת שיכולים להופיע בעקבות פתיחת הזיכרון.	[]	he	2026-07-07 09:00:00+00
3fa85f64-5717-4562-b3fc-2c963f66afa6	1691dd4c-a98c-5f5c-ba9e-54721deb7c12	b05b45ef-5564-5f2e-885e-47f1e7e1bf66	וואו, אינטגרציה מדהימה. המעבר המהיר מהימנעות כרונית לקבלת החלטה אקטיבית לחזור לארץ התקווה מראה על שבירה מלאה של דפוס הקהות הרגשית. התחברות מחדש לדמות האב דרך הכוכבים ולא דרך זיכרון המוות בקניון מסמנת אינטגרציה בריאה של הזיכרון. במפגש המעקב נתמקד במניעת נסיגה לנוכח הטריגרים הסביבתיים האמיתיים שיפגוש בממלכה הישנה.	[]	he	2026-07-14 09:00:00+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, auth_type, role, email, full_name, password_hash, token_version, created_at) FROM stdin;
\.


--
-- Name: calendar_events calendar_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calendar_events
    ADD CONSTRAINT calendar_events_pkey PRIMARY KEY (user_id, id);


--
-- Name: meeting_summaries meeting_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_summaries
    ADD CONSTRAINT meeting_summaries_pkey PRIMARY KEY (user_id, id);


--
-- Name: next_meeting_reports next_meeting_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.next_meeting_reports
    ADD CONSTRAINT next_meeting_reports_pkey PRIMARY KEY (user_id, id);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (user_id, id);


--
-- Name: transcripts transcripts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts
    ADD CONSTRAINT transcripts_pkey PRIMARY KEY (user_id, id);


--
-- Name: next_meeting_reports uq_reports_user_meeting; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.next_meeting_reports
    ADD CONSTRAINT uq_reports_user_meeting UNIQUE (user_id, meeting_id);


--
-- Name: meeting_summaries uq_summaries_user_meeting; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_summaries
    ADD CONSTRAINT uq_summaries_user_meeting UNIQUE (user_id, meeting_id);


--
-- Name: transcripts uq_transcripts_user_meeting; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts
    ADD CONSTRAINT uq_transcripts_user_meeting UNIQUE (user_id, meeting_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_calendar_events_user_end_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_calendar_events_user_end_at ON public.calendar_events USING btree (user_id, end_at);


--
-- Name: ix_calendar_events_user_start_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_calendar_events_user_start_at ON public.calendar_events USING btree (user_id, start_at);


--
-- Name: ix_meeting_summaries_meeting_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_meeting_summaries_meeting_id ON public.meeting_summaries USING btree (meeting_id);


--
-- Name: ix_next_meeting_reports_meeting_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_next_meeting_reports_meeting_id ON public.next_meeting_reports USING btree (meeting_id);


--
-- Name: ix_next_meeting_reports_user_patient; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_next_meeting_reports_user_patient ON public.next_meeting_reports USING btree (user_id, patient_id);


--
-- Name: ix_transcripts_meeting_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transcripts_meeting_id ON public.transcripts USING btree (meeting_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: meeting_summaries meeting_summaries_user_id_meeting_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meeting_summaries
    ADD CONSTRAINT meeting_summaries_user_id_meeting_id_fkey FOREIGN KEY (user_id, meeting_id) REFERENCES public.calendar_events(user_id, id) ON DELETE CASCADE;


--
-- Name: next_meeting_reports next_meeting_reports_user_id_meeting_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.next_meeting_reports
    ADD CONSTRAINT next_meeting_reports_user_id_meeting_id_fkey FOREIGN KEY (user_id, meeting_id) REFERENCES public.calendar_events(user_id, id) ON DELETE CASCADE;


--
-- Name: next_meeting_reports next_meeting_reports_user_id_patient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.next_meeting_reports
    ADD CONSTRAINT next_meeting_reports_user_id_patient_id_fkey FOREIGN KEY (user_id, patient_id) REFERENCES public.patients(user_id, id) ON DELETE CASCADE;


--
-- Name: transcripts transcripts_user_id_meeting_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts
    ADD CONSTRAINT transcripts_user_id_meeting_id_fkey FOREIGN KEY (user_id, meeting_id) REFERENCES public.calendar_events(user_id, id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict YPCP9CpbG0Vjjk2pwx25KZ9oRTbaLURmLzhgdwrNEBdaTJnL6Aml2ouFL4ZuELy

